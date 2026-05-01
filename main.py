
import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

from drive_utils import get_file_id_from_link, download_file_from_drive
from ads_utils import upload_to_meta, upload_to_snapchat, upload_to_tiktok

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# States
SELECT_PLATFORM, GET_DRIVE_LINK, CONFIRM_UPLOAD = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("مرحباً! استخدم /upload لبدء رفع الإعلانات.")
    return ConversationHandler.END

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [InlineKeyboardButton("Meta Ads", callback_data="meta")],
        [InlineKeyboardButton("Snapchat Ads", callback_data="snapchat")],
        [InlineKeyboardButton("TikTok Ads", callback_data="tiktok")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر المنصة:", reply_markup=reply_markup)
    return SELECT_PLATFORM

async def select_platform(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["platform"] = query.data
    await query.edit_message_text(f"تم اختيار {query.data}. أرسل رابط جوجل درايف:")
    return GET_DRIVE_LINK

async def get_drive_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    link = update.message.text
    file_id = get_file_id_from_link(link)
    if not file_id:
        await update.message.reply_text("رابط غير صالح. حاول مرة أخرى:")
        return GET_DRIVE_LINK
    
    context.user_data["drive_link"] = link
    context.user_data["file_id"] = file_id
    await update.message.reply_text(f"هل أنت متأكد من رفع الملف إلى {context.user_data['platform']}؟ (نعم/لا)")
    return CONFIRM_UPLOAD

async def confirm_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.lower() != "نعم":
        await update.message.reply_text("تم الإلغاء.")
        return ConversationHandler.END

    await update.message.reply_text("جارٍ التحميل من جوجل درايف...")
    file_id = context.user_data["file_id"]
    platform = context.user_data["platform"]
    local_path = f"temp_{file_id}"
    
    try:
        download_file_from_drive(file_id, local_path)
        await update.message.reply_text(f"تم التحميل. جارٍ الرفع إلى {platform}...")
        
        result = None
        if platform == "meta":
            result = upload_to_meta(local_path, "video") # Default to video for now
        elif platform == "snapchat":
            result = upload_to_snapchat(local_path, "video")
        elif platform == "tiktok":
            result = upload_to_tiktok(local_path)
            
        await update.message.reply_text(f"تمت العملية! النتيجة: {result}")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ: {str(e)}")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)
            
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("تم الإلغاء.")
    return ConversationHandler.END

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
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
    application.run_polling()

if __name__ == "__main__":
    main()
