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
SELECT_PLATFORM, GET_DRIVE_LINK, CONFIRM_UPLOAD = range(3)


async def start(update: Update, context) -> int:
    await update.message.reply_text(
        "مرحباً! 👋\n"
        "أنا بوت أتمتة الإعلانات.\n"
        "استخدم /upload لبدء رفع الإعلانات إلى المنصات الإعلانية.\n"
        "استخدم /cancel لإلغاء أي عملية جارية."
    )
    return ConversationHandler.END


async def upload_command(update: Update, context) -> int:
    keyboard = [
        [InlineKeyboardButton("📘 Meta Ads", callback_data="meta")],
        [InlineKeyboardButton("👻 Snapchat Ads", callback_data="snapchat")],
        [InlineKeyboardButton("🎵 TikTok Ads", callback_data="tiktok")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر المنصة الإعلانية:", reply_markup=reply_markup)
    return SELECT_PLATFORM


async def select_platform(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["platform"] = query.data
    platform_names = {
        "meta": "Meta Ads 📘",
        "snapchat": "Snapchat Ads 👻",
        "tiktok": "TikTok Ads 🎵"
    }
    name = platform_names.get(query.data, query.data)
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
        f"• معرّف الملف: `{file_id}`\n\n"
        "هل أنت متأكد من رفع الملف؟ أرسل *نعم* للتأكيد أو *لا* للإلغاء.",
        parse_mode="Markdown"
    )
    return CONFIRM_UPLOAD


async def confirm_upload(update: Update, context) -> int:
    response = update.message.text.strip().lower()
    if response not in ["نعم", "yes", "y"]:
        await update.message.reply_text("❌ تم الإلغاء. استخدم /upload للبدء من جديد.")
        return ConversationHandler.END

    await update.message.reply_text("⏳ جارٍ التحميل من Google Drive...")

    file_id = context.user_data["file_id"]
    platform = context.user_data["platform"]
    local_path = f"/tmp/temp_{file_id}"

    try:
        download_file_from_drive(file_id, local_path)
        await update.message.reply_text(f"✅ تم التحميل. جارٍ الرفع إلى {platform}...")

        result = None
        if platform == "meta":
            result = upload_to_meta(local_path, "video")
        elif platform == "snapchat":
            result = upload_to_snapchat(local_path, "video")
        elif platform == "tiktok":
            result = upload_to_tiktok(local_path)

        await update.message.reply_text(
            f"🎉 تمت العملية بنجاح!\n\nالنتيجة:\n`{result}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Upload error: {e}")
        await update.message.reply_text(
            f"❌ حدث خطأ أثناء العملية:\n`{str(e)}`\n\nحاول مرة أخرى أو تواصل مع المسؤول.",
            parse_mode="Markdown"
        )
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

    return ConversationHandler.END


async def cancel(update: Update, context) -> int:
    await update.message.reply_text("❌ تم الإلغاء. استخدم /upload للبدء من جديد.")
    return ConversationHandler.END


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN غير موجود في متغيرات البيئة!")

    application = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("upload", upload_command)],
        states={
            SELECT_PLATFORM: [CallbackQueryHandler(select_platform)],
            GET_DRIVE_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_drive_link)],
            CONFIRM_UPLOAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_upload)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    logger.info("البوت يعمل على Railway...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
