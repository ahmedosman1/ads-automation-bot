import os
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
from drive_utils import download_file_from_drive, get_file_id_from_link


# Load environment variables
load_dotenv()


# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# States
SELECT_PLATFORM, GET_DRIVE_LINK, CONFIRM_UPLOAD, GET_MULTI_LINKS = range(4)


async def start(update: Update, context) -> int:
    await update.message.reply_text(
        "مرحباً! 👋\n"
        "أنا بوت أتمتة الإعلانات.\n"
        "استخدم /upload لرفع ملف واحد.\n"
        "استخدم /upload_multi لرفع عدة ملفات دفعة واحدة.\n"
        "استخدم /cancel لإلغاء أي عملية جارية."
    )
    return ConversationHandler.END


async def upload_command(update: Update, context) -> int:
    keyboard = [
        [InlineKeyboardButton("Meta Ads 📘", callback_data="meta")],
        [InlineKeyboardButton("Snapchat Ads 👻", callback_data="snapchat")],
        [InlineKeyboardButton("TikTok Ads 🎵", callback_data="tiktok")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر المنصة الإعلانية:", reply_markup=reply_markup)
    return SELECT_PLATFORM


async def select_platform(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    platform = query.data
    context.user_data["platform"] = platform
    platform_names = {
        "meta": "Meta Ads 📘",
        "snapchat": "Snapchat Ads 👻",
        "tiktok": "TikTok Ads 🎵"
    }
    name = platform_names.get(platform, platform)
    await query.edit_message_text(
        f"✅ تم اختيار {name}\n\n"
        "أرسل رابط Google Drive للملف (صورة أو فيديو):"
    )
    return GET_DRIVE_LINK


async def get_drive_link(update: Update, context) -> int:
    link = update.message.text.strip()
    file_id = get_file_id_from_link(link)
    if not file_id:
        await update.message.reply_text(
            "❌ رابط غير صالح. تأكد أن الرابط من Google Drive وحاول مرة أخرى:"
        )
        return GET_DRIVE_LINK

    context.user_data["drive_link"] = link
    context.user_data["file_id"] = file_id
    platform = context.user_data["platform"]
    platform_names = {
        "meta": "Meta Ads 📘",
        "snapchat": "Snapchat Ads 👻",
        "tiktok": "TikTok Ads 🎵"
    }
    name = platform_names.get(platform, platform)
    await update.message.reply_text(
        f"📋 تفاصيل الرفع:\n"
        f"• المنصة: {name}\n"
        f"• رابط الملف: {link}\n\n"
        "هل تريد المتابعة؟ (نعم / لا)"
    )
    return CONFIRM_UPLOAD


def _detect_file_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return "video" if ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"] else "image"


async def _upload_file(local_path: str, platform: str) -> dict:
    file_type = _detect_file_type(local_path)
    if platform == "meta":
        return upload_to_meta(local_path, file_type)
    elif platform == "snapchat":
        return upload_to_snapchat(local_path, file_type)
    elif platform == "tiktok":
        return upload_to_tiktok(local_path)
    return {}


async def confirm_upload(update: Update, context) -> int:
    response = update.message.text.strip().lower()
    if response not in ["نعم", "yes", "y"]:
        await update.message.reply_text("❌ تم الإلغاء. استخدم /upload للبدء من جديد.")
        return ConversationHandler.END

    await update.message.reply_text("⏳ جارٍ التحميل من Google Drive...")

    file_id = context.user_data["file_id"]
    platform = context.user_data["platform"]
    base_path = f"/tmp/temp_{file_id}"
    local_path = base_path

    try:
        # FIX: capture returned path which includes the file extension
        local_path = download_file_from_drive(file_id, base_path)
        await update.message.reply_text("✅ تم التحميل. جارٍ الرفع...")

        result = await _upload_file(local_path, platform)

        await update.message.reply_text(
            f"🎉 تمت العملية بنجاح!\n\nالنتيجة:\n`{result}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in confirm_upload: {e}")
        await update.message.reply_text(
            f"❌ حدث خطأ أثناء العملية: `{e}`\nحاول مرة أخرى أو تواصل مع المسؤول.",
            parse_mode="Markdown"
        )
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

    return ConversationHandler.END


# --- Multi-file upload ---

async def upload_multi_command(update: Update, context) -> int:
    keyboard = [
        [InlineKeyboardButton("Meta Ads 📘", callback_data="meta")],
        [InlineKeyboardButton("Snapchat Ads 👻", callback_data="snapchat")],
        [InlineKeyboardButton("TikTok Ads 🎵", callback_data="tiktok")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر المنصة لرفع عدة ملفات:", reply_markup=reply_markup)
    return SELECT_PLATFORM


async def get_multi_links(update: Update, context) -> int:
    text = update.message.text.strip()
    links = [l.strip() for l in text.splitlines() if l.strip()]
    platform = context.user_data["platform"]

    if not links:
        await update.message.reply_text("❌ لم يتم إرسال أي روابط. حاول مرة أخرى:")
        return GET_MULTI_LINKS

    await update.message.reply_text(f"⏳ جارٍ معالجة {len(links)} ملف(ات)...")

    success_count = 0
    fail_count = 0

    for link in links:
        file_id = get_file_id_from_link(link)
        if not file_id:
            fail_count += 1
            await update.message.reply_text(f"⚠️ رابط غير صالح: {link}")
            continue

        base_path = f"/tmp/temp_{file_id}"
        local_path = base_path
        try:
            local_path = download_file_from_drive(file_id, base_path)
            await _upload_file(local_path, platform)
            success_count += 1
        except Exception as e:
            fail_count += 1
            logger.error(f"Error uploading {link}: {e}")
            await update.message.reply_text(f"❌ فشل رفع: {link}\nالسبب: {e}")
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)

    await update.message.reply_text(
        f"✅ انتهت العملية!\n"
        f"• نجح: {success_count}\n"
        f"• فشل: {fail_count}"
    )
    return ConversationHandler.END


async def cancel(update: Update, context) -> int:
    await update.message.reply_text("❌ تم الإلغاء.")
    return ConversationHandler.END


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(token).build()

    single_conv = ConversationHandler(
        entry_points=[CommandHandler("upload", upload_command)],
        states={
            SELECT_PLATFORM: [CallbackQueryHandler(select_platform)],
            GET_DRIVE_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_drive_link)],
            CONFIRM_UPLOAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_upload)],
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

    app.add_handler(CommandHandler("start", start))
    app.add_handler(single_conv)
    app.add_handler(multi_conv)

    logger.info("Bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
