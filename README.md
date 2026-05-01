# Telegram Ads Automation Bot

هذا البوت يقوم بتحميل الملفات من جوجل درايف ورفعها مباشرة إلى منصات الإعلانات (Meta, Snapchat, TikTok).

## المتطلبات
- حساب على [Render](https://render.com)
- توكن بوت تلجرام من @BotFather
- إعداد APIs لكل منصة (Google Cloud, Meta Developers, Snap Developers, TikTok Developers)

## خطوات النشر على Render
1. ارفع الكود على GitHub.
2. أنشئ "Background Worker" جديد على Render.
3. اربطه بمستودع GitHub الخاص بك.
4. أضف متغيرات البيئة (Environment Variables) الموجودة في ملف `.env`.
5. اضغط على Deploy.

## متغيرات البيئة المطلوبة
- `TELEGRAM_BOT_TOKEN`
- `GOOGLE_DRIVE_CLIENT_ID`
- `GOOGLE_DRIVE_CLIENT_SECRET`
- `GOOGLE_DRIVE_REFRESH_TOKEN`
- `META_ADS_ACCESS_TOKEN`
- `META_ADS_ACCOUNT_ID`
- `SNAPCHAT_ADS_CLIENT_ID`
- `SNAPCHAT_ADS_CLIENT_SECRET`
- `SNAPCHAT_ADS_REFRESH_TOKEN`
- `SNAPCHAT_ADS_AD_ACCOUNT_ID`
- `TIKTOK_ADS_ACCESS_TOKEN`
- `TIKTOK_ADS_ADVERTISER_ID`
