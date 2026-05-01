import os
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

# States
(
    SELECT_PLATFORM,
    GET_DRIVE_LINK,
    CONFIRM_UPLOAD,
    GET_MULTI_LINKS,
    GET_FOLDER_LINK,
    SELECT_SUBFOLDER,
) = range(6)

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


def _detect_file_type(path: str, mime_type: str = None) -> str:
    """Detect image or video using Drive mimeType first, then file extension."""
    if mime_type:
        if mime_type.startswith("video/"):
            return "video"
        if mime_type.startswith("image/"):
            return "image"
    ext = os.path.splitext(path)[1].lower()
    return "video" if ext in [".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"] else "image"


async def _upload_file(local_path: str, platform: str, mime_type: str = None) -> dict:
    """Run the blocking upload in a thread so the event loop isn't blocked."""
    file_type = _detect_file_type(local_path, mime_type)
    logger.info(f"Uploading {os.path.basename(local_path)} as {file_type} to {platform}")
    if platform == "meta":
        return await asyncio.to_thread(upload_to_meta, local_path, file_type)
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
        "/upload_folder — رفع فولدر كامل من Drive\n"
        "/cancel — إلغاء أي عملية"
    )
    return ConversationHandler.END


# ── Platform selector (shared) ────────────────────────────────────────────────

async def select_platform(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    platform = query.data
    context.user_data["platform"] = platform
    name = PLATFORM_NAMES.get(platform, platform)
    mode = context.user_data.get("mode", "single")

    if mode == "folder":
        await query.edit_message_text(f"✅ {name}\n\nأرسل رابط فولدر Google Drive:")
        return GET_FOLDER_LINK
    elif mode == "multi":
        await query.edit_message_text(f"✅ {name}\n\nأرسل الروابط (كل رابط في سطر):")
        return GET_MULTI_LINKS
    else:
        await query.edit_message_text(f"✅ {name}\n\nأرسل رابط Google Drive للملف:")
        return GET_DRIVE_LINK


# ── Single file upload ────────────────────────────────────────────────────────

async def upload_command(update: Update, context) -> int:
    context.user_data["mode"] = "single"
    await update.message.reply_text("اختر المنصة:", reply_markup=PLATFORM_KEYBOARD)
    return SELECT_PLATFORM


async def get_drive_link(update: Update, context) -> int:
    link = update.message.text.strip()
    file_id = get_file_id_from_link(link)
    if not file_id:
        await update.message.reply_text("❌ رابط غير صالح. أرسل رابط Google Drive صحيح:")
        return GET_DRIVE_LINK
    context.user_data["file_id"] = file_id
    name = PLATFORM_NAMES.get(context.user_data["platform"], "")
    await update.message.reply_text(
        f"📋 المنصة: {name}\nالرابط: {link}\n\nهل تريد المتابعة؟ (نعم / لا)"
    )
    return CONFIRM_UPLOAD


async def confirm_upload(update: Update, context) -> int:
    if update.message.text.strip().lower() not in ["نعم", "yes", "y"]:
        await update.message.reply_text("❌ تم الإلغاء.")
        return ConversationHandler.END

    await update.message.reply_text("⏳ جارٍ التحميل من Google Drive...")
    file_id = context.user_data["file_id"]
    platform = context.user_data["platform"]
    base_path = f"/tmp/temp_{file_id}"
    local_path = base_path
    try:
        local_path = await asyncio.to_thread(download_file_from_drive, file_id, base_path)
        await update.message.reply_text("✅ تم التحميل. جارٍ الرفع...")
        result = await _upload_file(local_path, platform)
        await update.message.reply_text(
            f"🎉 تمت العملية بنجاح!\n`{result}`", parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"confirm_upload error: {e}")
        await update.message.reply_text(f"❌ خطأ: `{e}`", parse_mode="Markdown")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)
    return ConversationHandler.END


# ── Multi-link upload ─────────────────────────────────────────────────────────

async def upload_multi_command(update: Update, context) -> int:
    context.user_data["mode"] = "multi"
    await update.message.reply_text("اختر المنصة:", reply_markup=PLATFORM_KEYBOARD)
    return SELECT_PLATFORM


async def get_multi_links(update: Update, context) -> int:
    links = [l.strip() for l in update.message.text.strip().splitlines() if l.strip()]
    platform = context.user_data["platform"]
    if not links:
        await update.message.reply_text("❌ لم يتم إرسال روابط. حاول مرة أخرى:")
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
        try:
            local_path = await asyncio.to_thread(download_file_from_drive, file_id, base_path)
            await _upload_file(local_path, platform)
            ok += 1
        except Exception as e:
            fail += 1
            logger.error(f"multi upload error {link}: {e}")
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
        await update.message.reply_text("❌ رابط غير صالح. أرسل رابط فولدر Google Drive:")
        return GET_FOLDER_LINK

    context.user_data["folder_id"] = folder_id
    await update.message.reply_text("⏳ جارٍ تحميل قائمة الفولدرات...")

    try:
        subfolders = await asyncio.to_thread(list_subfolders, folder_id)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في الوصول للفولدر: {e}")
        return ConversationHandler.END

    context.user_data["subfolders"] = subfolders

    rows = []
    for i, folder in enumerate(subfolders[:48]):
        rows.append([InlineKeyboardButton(f"📁 {folder['name']}", callback_data=f"sf:{i}")])
    rows.append([InlineKeyboardButton("📂 رفع كل الملفات في هذا الفولدر مباشرة", callback_data="sf:all")])

    msg = (
        f"وجدت {len(subfolders)} فولدر فرعي. اختر فولدراً للرفع:"
        if subfolders else
        "لا توجد فولدرات فرعية. اضغط لرفع كل الملفات:"
    )
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(rows))
    return SELECT_SUBFOLDER


async def select_subfolder(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data
    root_folder_id = context.user_data["folder_id"]
    platform = context.user_data["platform"]
    subfolders = context.user_data.get("subfolders", [])

    if data == "sf:all":
        target_id = root_folder_id
        folder_name = "الفولدر الرئيسي"
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
        await query.message.reply_text("❌ لا توجد ملفات في هذا الفولدر.")
        return ConversationHandler.END

    # Separate images and videos for reporting
    images = [f for f in files if f.get("mimeType", "").startswith("image/")]
    videos = [f for f in files if f.get("mimeType", "").startswith("video/")]
    others = [f for f in files if not f.get("mimeType", "").startswith(("image/", "video/"))]

    await query.message.reply_text(
        f"📊 فولدر «{folder_name}»:\n"
        f"• صور: {len(images)}\n"
        f"• فيديوهات: {len(videos)}\n"
        f"• أخرى: {len(others)}\n"
        f"المجموع: {len(files)} ملف\n\n"
        f"⏳ جارٍ الرفع واحداً واحداً..."
    )

    ok_img = ok_vid = fail = 0

    for file_info in files:
        file_id = file_info["id"]
        file_name = file_info["name"]
        mime_type = file_info.get("mimeType", "")
        local_path = f"/tmp/{file_name}"

        try:
            # Download in thread (non-blocking)
            await asyncio.to_thread(download_file_by_name, file_id, file_name, "/tmp")
            # Upload in thread with correct type from mimeType
            await _upload_file(local_path, platform, mime_type)

            if mime_type.startswith("video/"):
                ok_vid += 1
                logger.info(f"✅ Video uploaded: {file_name}")
            else:
                ok_img += 1
                logger.info(f"✅ Image uploaded: {file_name}")

        except Exception as e:
            fail += 1
            logger.error(f"Error uploading {file_name}: {e}")
            await query.message.reply_text(f"⚠️ فشل: {file_name}\n{e}")
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)

    await query.message.reply_text(
        f"✅ انتهى رفع فولدر «{folder_name}»\n"
        f"• صور تم رفعها: {ok_img}\n"
        f"• فيديوهات تم رفعها: {ok_vid}\n"
        f"• فشل: {fail}"
    )
    return ConversationHandler.END


# ── Cancel ────────────────────────────────────────────────────────────────────

async def cancel(update: Update, context) -> int:
    await update.message.reply_text("❌ تم الإلغاء.")
    return ConversationHandler.END


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(token).build()

    single_conv = ConversationHandler(
        entry_points=[CommandHandler("upload", upload_command)],
        states={
            SELECT_PLATFORM: [CallbackQueryHandler(select_platform)],
            GET_DRIVE_LINK:  [MessageHandler(filters.TEXT & ~filters.COMMAND, get_drive_link)],
            CONFIRM_UPLOAD:  [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_upload)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    multi_conv = ConversationHandler(
        entry_points=[CommandHandler("upload_multi", upload_multi_command)],
        states={
            SELECT_PLATFORM: [CallbackQueryHandler(select_platform)],
            GET_MULTI_LINKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_multi_links)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    folder_conv = ConversationHandler(
        entry_points=[CommandHandler("upload_folder", upload_folder_command)],
        states={
            SELECT_PLATFORM:  [CallbackQueryHandler(select_platform)],
            GET_FOLDER_LINK:  [MessageHandler(filters.TEXT & ~filters.COMMAND, get_folder_link)],
            SELECT_SUBFOLDER: [CallbackQueryHandler(select_subfolder, pattern="^sf:")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(single_conv)
    app.add_handler(multi_conv)
    app.add_handler(folder_conv)

    logger.info("Bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
