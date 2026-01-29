# Authored By Certified Coders 2026
# Module: Repo/Source Info - Updated Support Link

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from AnnieXMedia import app
from config import BOT_USERNAME, OWNER_ID

# الصورة الاحتياطية
FALLBACK_PHOTO = "https://files.catbox.moe/z15chx.jpg"

# نص السورس
repo_caption = """
<b>• اهلا بك في معلومات السورس
• يقدم لك السورس تجربة استماع مميزة
• سيرفرات قوية تعمل 24/7 بدون تقطيع
• حماية كاملة من الحظر والمشاكل
• تحديثات مستمرة لضمان الاستقرار

• للتنصيب او الاستفسار تواصل مع المطور</b>
"""

@app.on_message(filters.command(["repo", "سورس", "السورس", "يا سورس"], prefixes=["", "/", "!", "."]))
async def show_repo(client, msg):
    
    # رابط الدعم الجديد
    support_link = "https://t.me/music0587"

    buttons = [
        [
            InlineKeyboardButton(
                "اضف البوت لمجموعتك", 
                url=f"https://t.me/{BOT_USERNAME}?startgroup=true"
            )
        ],
        [
            InlineKeyboardButton("المطور", url="https://t.me/S_G0C7"),
            InlineKeyboardButton("الدعم الفني", url=support_link)
        ]
    ]

    reply_markup = InlineKeyboardMarkup(buttons)
    
    # منطق تحديد الصورة
    photo_to_send = FALLBACK_PHOTO  # الافتراضي
    
    # محاولة جلب صورة المستخدم
    if msg.from_user:
        try:
            async for photo in client.get_chat_photos(msg.from_user.id, limit=1):
                photo_to_send = photo.file_id
        except Exception:
            pass 

    try:  
        await msg.reply_photo(
            photo=photo_to_send,
            caption=repo_caption,
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Repo Error: {e}")
        try:
            await msg.reply_photo(
                photo=FALLBACK_PHOTO,
                caption=repo_caption,
                reply_markup=reply_markup
            )
        except:
            pass
