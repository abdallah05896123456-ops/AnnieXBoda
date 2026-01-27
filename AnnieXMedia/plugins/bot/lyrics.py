# Authored By Certified Coders 2026
# LYRICS SYSTEM - SUPREME MONGODB EDITION
# High Performance - Detailed Responses - No Emojis

import asyncio
import random
import re
import string
import lyricsgenius as lg
from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from motor.motor_asyncio import AsyncIOMotorClient

from AnnieXMedia import app
import config
from config import BANNED_USERS, MONGO_DB_URI

# ==========================================
# إعدادات قاعدة البيانات والمحرك
# ==========================================

# الاتصال بقاعدة بيانات مونجو
mongo_client = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo_client.Annie
lyrics_col = db.lyrics_cache

# إعدادات جينيوس
GENIUS_API_KEY = "Blj6yk-JqhAt91CNQt3D31eWcnt5zqYBsx2uIKk9JXr8qrmlCmnLkq8R4RV7XG8f0Afi1ODQ-EDVuVT6mM3uBQ"
LYRICS_STATUS = True
SUDO_USERS = config.OWNER_ID if isinstance(config.OWNER_ID, list) else [config.OWNER_ID]

genius_engine = lg.Genius(
    GENIUS_API_KEY, 
    skip_non_songs=True, 
    excluded_terms=["(Remix)", "(Live)", "(Edit)"], 
    remove_section_headers=True
)
genius_engine.verbose = False
genius_engine.timeout = 20

# ==========================================
# دالات التعامل مع قاعدة البيانات
# ==========================================

async def save_lyrics_to_db(lyric_hash, title, artist, content):
    """حفظ كلمات الأغنية في قاعدة البيانات بشكل دائم"""
    await lyrics_col.update_one(
        {"_id": lyric_hash},
        {"$set": {
            "title": title,
            "artist": artist,
            "content": content,
            "timestamp": time.time()
        }},
        upsert=True
    )

async def get_lyrics_from_db(lyric_hash):
    """استرجاع الكلمات من قاعدة البيانات باستخدام الهاش"""
    data = await lyrics_col.find_one({"_id": lyric_hash})
    return data["content"] if data else None

# ==========================================
# دالات المعالجة والتنظيف
# ==========================================

def clean_lyrics_text(raw_lyrics):
    if not raw_lyrics:
        return ""
    processed = re.sub(r"^.*?Lyrics", "", raw_lyrics, flags=re.DOTALL)
    processed = processed.replace("You might also like", "")
    processed = re.sub(r"\d*Embed", "", processed)
    processed = re.sub(r"[0-9]+$", "", processed)
    return processed.strip()

# ==========================================
# أوامر التحكم (للمطور فقط)
# ==========================================

@app.on_message(filters.regex(r"^(قفل الكلمات|فتح الكلمات)$") & filters.user(SUDO_USERS))
async def toggle_lyrics_system(_, message: Message):
    global LYRICS_STATUS
    if "قفل" in message.text:
        LYRICS_STATUS = False
        await message.reply_text("لقد تم إيقاف تشغيل نظام البحث عن كلمات الأغاني بنجاح من قبل الإدارة ولن يتمكن الأعضاء من استخدامه حتى إشعار آخر.")
    else:
        LYRICS_STATUS = True
        await message.reply_text("لقد تم تفعيل نظام البحث عن كلمات الأغاني مجددا وبإمكان كافة المستخدمين الآن الاستفادة من الخدمة.")

# ==========================================
# معالج البحث الرئيسي
# ==========================================

@app.on_message(filters.regex(r"^(كلمات )") & ~BANNED_USERS)
async def lyrics_search_engine(client, message: Message):
    if not LYRICS_STATUS and message.from_user.id not in SUDO_USERS:
        return await message.reply_text("نعتذر منك ولكن هذا القسم مغلق حاليا لغرض الصيانة أو بقرار من مبرمج البوت يرجى المحاولة في وقت لاحق.")

    try:
        search_query = message.text.split(None, 1)[1].strip()
    except IndexError:
        return await message.reply_text("يرجى إدراج اسم الأغنية المطلوب البحث عنها بعد الأمر مباشرة لكي يتمكن النظام من بدء عملية الاستخراج.")
        
    status_msg = await message.reply_text("جاري البدء في عملية البحث الموسعة داخل قاعدة بيانات جينيوس العالمية يرجى الانتظار قليلا.")
    
    try:
        loop = asyncio.get_event_loop()
        song = await loop.run_in_executor(None, lambda: genius_engine.search_song(search_query))
        
        if not song or not song.lyrics:
            return await status_msg.edit(f"لم يتم العثور على أي نتائج تطابق بحثك عن {search_query} يرجى التأكد من كتابة الاسم بشكل صحيح.")

        final_text = clean_lyrics_text(song.lyrics)
        if not final_text:
            return await status_msg.edit("لم يتم النجاح في استخراج النص المطلوب نظرا لوجود خلل في المصدر الرئيسي للكلمات.")

        # توليد هاش وحفظ البيانات في مونجو
        import time
        ran_hash = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
        await save_lyrics_to_db(ran_hash, song.title, song.artist, final_text)

        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(text="عرض نص الكلمات بالكامل", url=f"https://t.me/{app.username}?start=lyrics_{ran_hash}")]
        ])
        
        await status_msg.edit(
            f"لقد تم الانتهاء من عملية البحث بنجاح واستخراج الكلمات المطلوبة.\n\nاسم العمل الفني: {song.title}\nاسم الفنان صاحب العمل: {song.artist}",
            reply_markup=buttons
        )
    
    except Exception as error:
        print(f"Lyrics DB Error: {error}")
        await status_msg.edit("حدث خطأ غير متوقع أثناء محاولة الاتصال بخوادم جينيوس أو قاعدة البيانات يرجى إعادة المحاولة لاحقا.")

# ==========================================
# معالج العرض (Deep Link) من قاعدة البيانات
# ==========================================

@app.on_message(filters.regex(r"^/start lyrics_") & ~BANNED_USERS, group=-1)
async def lyrics_db_display(client, message: Message):
    try:
        lyrics_hash = message.text.split("lyrics_")[1]
        # جلب الكلمات من المونجو مباشرة
        content = await get_lyrics_from_db(lyrics_hash)
        
        if not content:
            return await message.reply_text("لم يتم العثور على البيانات المطلوبة في قاعدة البيانات ربما تم حذفها أو أن الرابط قديم جدا.")
        
        if len(content) > 4000:
            content = content[:4000] + "\n\n(تم اقتطاع جزء من النص نظرا لتجاوزه الحد المسموح به في رسائل تليجرام)."
            
        await message.reply_text(
            f"إليك الكلمات الكاملة للعمل الفني الذي بحثت عنه:\n\n{content}",
            disable_web_page_preview=True
        )
        message.stop_propagation()
    except:
        pass
