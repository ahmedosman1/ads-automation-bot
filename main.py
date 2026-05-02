import os
import json
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)
from dotenv import load_dotenv
from ads_utils import upload_to_meta, upload_to_snapchat, upload_to_tiktok
from drive_utils import (
    download_file_from_drive,
    download_file_by_name,
    get_file_id_from_link,
    get_folder_id_from_link,
    list_subfolders,
    list_files_in_folder,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

(
    SELECT_PLATFORM,
    SELECT_META_ACCOUNT,
    GET_DRIVE_LINK,
    CONFIRM_UPLOAD,
    GET_MULTI_LINKS,
    GET_FOLDER_LINK,
    SELECT_SUBFOLDER,
) = range(7)

PLATFORM_NAMES = {
    "meta": "Meta Ads 📘",
    "snapchat": "Snapchat Ads 👻",
    "tiktok": "TikTok Ads 🎵",
}

PLATFORM_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("Meta Ads 📘", callback_data="meta")],
    [InlineKeyboardButton("Snapchat Ads 👻", callback_data="snapchat")],
    [InlineKeyboardButton("TikTok Ads 🎵", callback_data="tiktok")],
])


# ── Multi-account helpers ─────────────────────────────────────────────────────

def get_meta_accounts() -> list:
    """Load Meta accounts from META_ACCOUNTS JSON env var.
    Falls back to single account from META_ADS_ACCESS_TOKEN + META_ADS_ACCOUNT_ID.
    """
    raw = os.getenv("META_ACCOUNTS", "").strip()
    if raw:
        try:
            accounts = json.loads(raw)
            if isinstance(accounts, list) and accounts:
                return accounts
        except json.JSONDecodeError:
            logger.warning("META_ACCOUNTS is not valid JSON, falling back to single account")

    # Fallback: single account from individual env vars
    token = os.getenv("META_ADS_ACCESS_TOKEN", "")
    account_id = os.getenv("META_ADS_ACCOUNT_ID", "")
    if token and account_id:
        return [{"name": "Default", "account_id": account_id, "token": token}]
    return []


# ── File type helpers ─────────────────────────────────────────────────────────

def _detect_file_type(mime_type: str, path: str = "") -> str:
    if mime_type:
        if mime_type.startswith("video/"):
            return "video"
        if mime_type.startswith("image/"):
            return "image"
    ext = os.path.splitext(path)[1].lower()
    video_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".3gp", ".wmv", ".flv", ".ts", ".mts"}
    return "video" if ext in video_exts else "image"


async def _upload_file(local_path: str, platform: str, mime_type: str = "",
                       meta_account: dict = None) -> dict:
    file_type = _detect_file_type(mime_type, local_path)
    logger.info(f"Uploading '{os.path.basename(local_path)}' | {file_type} | {platform}")
    if platform == "meta":
        account_id = (meta_account or {}).get("account_id") or os.getenv("META_ADS_ACCOUNT_ID")
        token = (meta_account or {}).get("token") or os.getenv("META_ADS_ACCESS_TOKEN")
        return await asyncio.to_thread(upload_to_meta, local_path, file_type, account_id, token)
    elif platform == "snapchat":
        return await asyncio.to_thread(upload_to_snapchat, local_path, file_type)
    elif platform == "tiktok":
        return await asyncio.to_thread(upload_to_tiktok, local_path)
    return {}


# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, context) -> int:
    await update.message.reply_text(
        "مرحباً! 👋 أنا بوت أتمتة الإعلانات.\n\n"
        "/upload — رفع ملف واحد\n"
        "/upload_multi — رفع روابط متعددة\n"
        "/upload_folder — رفع فولدر كامل\n"
        "/accounts — عرض الأكونتات المتاحة\n"
        "/cancel — إلغاء"
    )
    return ConversationHandler.END


async def accounts_command(update: Update, context) -> int:
    accounts = get_meta_accounts()
    if not accounts:
        await update.message.reply_text("❌ لا توجد أكونتات Meta مضافة.")
        return ConversationHandler.END
    lines = "\n".join(f"• {a['name']} — {a['account_id']}" for a in accounts)
    await update.message.reply_text(f"📋 أكونتات Meta المتاحة:\n{lines}")
    return ConversationHandler.END


# ── Platform selector ─────────────────────────────────────────────────────────

async def select_platform(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    platform = query.data
    context.user_data["platform"] = platform
    name = PLATFORM_NAMES.get(platform, platform)
    mode = context.user_data.get("mode", "single")

    # If Meta with multiple accounts → show account selector first
    if platform == "meta":
        accounts = get_meta_accounts()
        if len(accounts) > 1:
            context.user_data["meta_accounts"] = accounts
            rows = [
                [InlineKeyboardButton(f"📘 {a['name']}", callback_data=f"ma:{i}")]
                for i, a in enumerate(accounts)
            ]
            rows.append([InlineKeyboardButton("📘 كل الأكونتات", callback_data="ma:all")])
            await query.edit_message_text(
                f"✅ {name}\n\nاختر الأكونت:",
                reply_markup=InlineKeyboardMarkup(rows)
            )
            return SELECT_META_ACCOUNT
        elif len(accounts) == 1:
            context.user_data["meta_account"] = accounts[0]

    # Proceed to file input based on mode
    if mode == "folder":
        await query.edit_message_text(f"✅ {name}\n\nأرسل رابط فولدر Google Drive:")
        return GET_FOLDER_LINK
    elif mode == "multi":
        await query.edit_message_text(f"✅ {name}\n\nأرسل الروابط (كل رابط في سطر):")
        return GET_MULTI_LINKS
    else:
        await query.edit_message_text(f"✅ {name}\n\nأرسل رابط Google Drive للملف:")
        return GET_DRIVE_LINK


async def select_meta_account(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data   # "ma:0", "ma:1", ... or "ma:all"
    accounts = context.user_data.get("meta_accounts", [])
    mode = context.user_data.get("mode", "single")

    if data == "ma:all":
        context.user_data["meta_account"] = None   # will loop all accounts
        context.user_data["meta_accounts_all"] = True
    else:
        idx = int(data.split(":")[1])
        context.user_data["meta_account"] = accounts[idx]
        context.user_data["meta_accounts_all"] = False

    label = "كل الأكونتات" if data == "ma:all" else accounts[int(data.split(":")[1])]["name"]

    if mode == "folder":
        await query.edit_message_text(f"✅ {label}\n\nأرسل رابط فولدر Google Drive:")
        return GET_FOLDER_LINK
    elif mode == "multi":
        await query.edit_message_text(f"✅ {label}\n\nأرسل الروابط (كل رابط في سطر):")
        return GET_MULTI_LINKS
    else:
        await query.edit_message_text(f"✅ {label}\n\nأرسل رابط Google Drive للملف:")
        return GET_DRIVE_LINK


# ── Single file ───────────────────────────────────────────────────────────────

async def upload_command(update: Update, context) -> int:
    context.user_data["mode"] = "single"
    await update.message.reply_text("اختر المنصة:", reply_markup=PLATFORM_KEYBOARD)
    return SELECT_PLATFORM


async def get_drive_link(update: Update, context) -> int:
    link = update.message.text.strip()
    file_id = get_file_id_from_link(link)
    if not file_id:
        await update.message.reply_text("❌ رابط غير صالح:")
        return GET_DRIVE_LINK
    context.user_data["file_id"] = file_id
    name = PLATFORM_NAMES.get(context.user_data["platform"], "")
    account = context.user_data.get("meta_account")
    account_label = f" ({account['name']})" if account else ""
    await update.message.reply_text(
        f"📋 المنصة: {name}{account_label}\nالرابط: {link}\n\nهل تريد المتابعة؟ (نعم / لا)"
    )
    return CONFIRM_UPLOAD


async def confirm_upload(update: Update, context) -> int:
    if update.message.text.strip().lower() not in ["نعم", "yes", "y"]:
        await update.message.reply_text("❌ تم الإلغاء.")
        return ConversationHandler.END

    await update.message.reply_text("⏳ جارٍ التحميل من Google Drive...")
    file_id = context.user_data["file_id"]
    platform = context.user_data["platform"]
    local_path = f"/tmp/temp_{file_id}"
    mime_type = ""
    try:
        local_path, mime_type = await asyncio.to_thread(download_file_from_drive, file_id, local_path)
        await update.message.reply_text("✅ تم التحميل. جارٍ الرفع...")

        accounts_all = context.user_data.get("meta_accounts_all", False)
        if platform == "meta" and accounts_all:
            accounts = context.user_data.get("meta_accounts", [])
            ok = fail = 0
            for acc in accounts:
                try:
                    await _upload_file(local_path, platform, mime_type, acc)
                    ok += 1
                except Exception as e:
                    fail += 1
                    await update.message.reply_text(f"⚠️ {acc['name']}: {e}")
            await update.message.reply_text(f"🎉 انتهى!\n• نجح: {ok}\n• فشل: {fail}")
        else:
            meta_account = context.user_data.get("meta_account")
            result = await _upload_file(local_path, platform, mime_type, meta_account)
            await update.message.reply_text(f"🎉 تمت العملية بنجاح!\n`{result}`", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"confirm_upload error: {e}")
        await update.message.reply_text(f"❌ خطأ: `{e}`", parse_mode="Markdown")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)
    return ConversationHandler.END


# ── Multi-link ────────────────────────────────────────────────────────────────

async def upload_multi_command(update: Update, context) -> int:
    context.user_data["mode"] = "multi"
    await update.message.reply_text("اختر المنصة:", reply_markup=PLATFORM_KEYBOARD)
    return SELECT_PLATFORM


async def get_multi_links(update: Update, context) -> int:
    links = [l.strip() for l in update.message.text.strip().splitlines() if l.strip()]
    platform = context.user_data["platform"]
    meta_account = context.user_data.get("meta_account")
    accounts_all = context.user_data.get("meta_accounts_all", False)
    meta_accounts = context.user_data.get("meta_accounts", [])

    if not links:
        await update.message.reply_text("❌ لم يتم إرسال روابط:")
        return GET_MULTI_LINKS

    await update.message.reply_text(f"⏳ جارٍ معالجة {len(links)} ملف(ات)...")
    ok = fail = 0
    for link in links:
        file_id = get_file_id_from_link(link)
        if not file_id:
            fail += 1
            await update.message.reply_text(f"⚠️ رابط غير صالح: {link}")
            continue
        base_path = f"/tmp/temp_{file_id}"
        local_path = base_path
        mime_type = ""
        try:
            local_path, mime_type = await asyncio.to_thread(download_file_from_drive, file_id, base_path)
            if platform == "meta" and accounts_all:
                for acc in meta_accounts:
                    await _upload_file(local_path, platform, mime_type, acc)
            else:
                await _upload_file(local_path, platform, mime_type, meta_account)
            ok += 1
        except Exception as e:
            fail += 1
            await update.message.reply_text(f"❌ فشل: {link}\n{e}")
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)
    await update.message.reply_text(f"✅ انتهى!\n• نجح: {ok}\n• فشل: {fail}")
    return ConversationHandler.END


# ── Folder upload ─────────────────────────────────────────────────────────────

async def upload_folder_command(update: Update, context) -> int:
    context.user_data["mode"] = "folder"
    await update.message.reply_text("اختر المنصة:", reply_markup=PLATFORM_KEYBOARD)
    return SELECT_PLATFORM


async def get_folder_link(update: Update, context) -> int:
    link = update.message.text.strip()
    folder_id = get_folder_id_from_link(link)
    if not folder_id:
        await update.message.reply_text("❌ رابط غير صالح:")
        return GET_FOLDER_LINK
    context.user_data["folder_id"] = folder_id
    await update.message.reply_text("⏳ جارٍ تحميل قائمة الفولدرات...")
    try:
        subfolders = await asyncio.to_thread(list_subfolders, folder_id)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")
        return ConversationHandler.END
    context.user_data["subfolders"] = subfolders
    rows = [[InlineKeyboardButton(f"📁 {f['name']}", callback_data=f"sf:{i}")] for i, f in enumerate(subfolders[:48])]
    rows.append([InlineKeyboardButton("📂 رفع كل الملفات مباشرة", callback_data="sf:all")])
    msg = f"وجدت {len(subfolders)} فولدر فرعي. اختر:" if subfolders else "لا توجد فولدرات فرعية:"
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(rows))
    return SELECT_SUBFOLDER


async def select_subfolder(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    root_folder_id = context.user_data["folder_id"]
    platform = context.user_data["platform"]
    meta_account = context.user_data.get("meta_account")
    accounts_all = context.user_data.get("meta_accounts_all", False)
    meta_accounts = context.user_data.get("meta_accounts", [])
    subfolders = context.user_data.get("subfolders", [])

    if data == "sf:all":
        target_id, folder_name = root_folder_id, "الفولدر الرئيسي"
    else:
        idx = int(data.split(":")[1])
        target_id = subfolders[idx]["id"]
        folder_name = subfolders[idx]["name"]

    await query.edit_message_text(f"⏳ جارٍ جلب ملفات: {folder_name}...")
    try:
        files = await asyncio.to_thread(list_files_in_folder, target_id)
    except Exception as e:
        await query.message.reply_text(f"❌ خطأ: {e}")
        return ConversationHandler.END
    if not files:
        await query.message.reply_text("❌ لا توجد ملفات.")
        return ConversationHandler.END

    images = [f for f in files if f.get("mimeType", "").startswith("image/")]
    videos = [f for f in files if f.get("mimeType", "").startswith("video/")]
    acc_label = "كل الأكونتات" if accounts_all else (meta_account["name"] if meta_account else "")
    await query.message.reply_text(
        f"📊 «{folder_name}» {'→ ' + acc_label if acc_label else ''}\n"
        f"• صور: {len(images)} | فيديوهات: {len(videos)}\n⏳ جارٍ الرفع..."
    )

    ok_img = ok_vid = fail = 0
    for file_info in files:
        file_id = file_info["id"]
        file_name = file_info["name"]
        mime_type = file_info.get("mimeType", "")
        local_path = f"/tmp/{file_name}"
        try:
            await asyncio.to_thread(download_file_by_name, file_id, file_name, "/tmp")
            if platform == "meta" and accounts_all:
                for acc in meta_accounts:
                    await _upload_file(local_path, platform, mime_type, acc)
            else:
                await _upload_file(local_path, platform, mime_type, meta_account)
            if mime_type.startswith("video/"):
                ok_vid += 1
            else:
                ok_img += 1
        except Exception as e:
            fail += 1
            await query.message.reply_text(f"⚠️ فشل: {file_name}\n{e}")
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)

    await query.message.reply_text(
        f"✅ انتهى «{folder_name}»\n• صور: {ok_img}\n• فيديوهات: {ok_vid}\n• فشل: {fail}"
    )
    return ConversationHandler.END


async def cancel(update: Update, context) -> int:
    await update.message.reply_text("❌ تم الإلغاء.")
    return ConversationHandler.END


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(token).build()

    shared_states = {
        SELECT_PLATFORM:     [CallbackQueryHandler(select_platform)],
        SELECT_META_ACCOUNT: [CallbackQueryHandler(select_meta_account, pattern="^ma:")],
    }

    single_conv = ConversationHandler(
        entry_points=[CommandHandler("upload", upload_command)],
        states={
            **shared_states,
            GET_DRIVE_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_drive_link)],
            CONFIRM_UPLOAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_upload)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    multi_conv = ConversationHandler(
        entry_points=[CommandHandler("upload_multi", upload_multi_command)],
        states={
            **shared_states,
            GET_MULTI_LINKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_multi_links)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    folder_conv = ConversationHandler(
        entry_points=[CommandHandler("upload_folder", upload_folder_command)],
        states={
            **shared_states,
            GET_FOLDER_LINK:  [MessageHandler(filters.TEXT & ~filters.COMMAND, get_folder_link)],
            SELECT_SUBFOLDER: [CallbackQueryHandler(select_subfolder, pattern="^sf:")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("accounts", accounts_command))
    app.add_handler(single_conv)
    app.add_handler(multi_conv)
    app.add_handler(folder_conv)

    logger.info("Bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
