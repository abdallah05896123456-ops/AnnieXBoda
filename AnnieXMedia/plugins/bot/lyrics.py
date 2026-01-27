# Authored By Certified Coders 2026
# LYRICS SYSTEM - MONGODB INTEGRATED
# Official API Auth - Formal Responses

import asyncio, random, re, string, time
import lyricsgenius as lg
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from motor.motor_asyncio import AsyncIOMotorClient
from AnnieXMedia import app
import config
from config import BANNED_USERS, MONGO_DB_URI

# ربط قاعدة البيانات
mongo_client = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo_client.Annie
lyrics_col = db.lyrics_cache

# توكن الوصول الرسمي لخدمة جينيوس
GENIUS_API_KEY = "WbhEqtER5NoCKr50VdOFyhk6Rtwgk-lVenk_E3iKmADpADtzDB19oU8wZA5pcDbVzt4l9g_G7Ft8uEdX4ecLvw"

genius_engine = lg.Genius(GENIUS_API_KEY, skip_non_songs=True, remove_section_headers=True)
genius_engine.verbose = False
genius_engine.timeout = 20

SUDO_USERS = config.OWNER_ID if isinstance(config.OWNER_ID, list) else [config.OWNER_ID]
LYRICS_STATUS = True

def clean_content(raw):
    """تطهير النص من المخلفات البرمجية للموقع"""
    if not raw: return ""
    p = re.sub(r"^.*?Lyrics", "", raw, flags=re.DOTALL)
    p = p.replace("You might also like", "")
    p = re.sub(r"\d*Embed", "", p)
    return p.strip()

@app.on_message(filters.regex(r"^(قفل الكلمات|فتح الكلمات)$") & filters.user(SUDO_USERS))
async def lyrics_control_switch(_, m: Message):
    global LYRICS_STATUS
    LYRICS_STATUS = "فتح" in m.text
    await m.reply_text(f"تمت عملية {'تفعيل' if LYRICS_STATUS else 'تعطيل'} النظام.")

@app.on_message(filters.regex(r"^(كلمات )") & ~BANNED_USERS)
async def lyrics_search_engine(client, m: Message):
    if not LYRICS_STATUS and m.from_user.id not in SUDO_USERS:
        return await m.reply_text("هذا القسم غير متاح حاليا.")

    query = m.text.split(None, 1)[1].strip()
    status = await m.reply_text("يتم الان البحث في قاعدة البيانات")
    
    try:
        loop = asyncio.get_event_loop()
        song = await loop.run_in_executor(None, lambda: genius_engine.search_song(query))
        
        if not song:
            return await status.edit("لم يتم العثور على نتائج.")

        text = clean_content(song.lyrics)
        r_hash = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
        
        # التخزين الدائم في MongoDB
        await lyrics_col.update_one(
            {"_id": r_hash}, 
            {"$set": {"t": song.title, "a": song.artist, "c": text, "d": time.time()}}, 
            upsert=True
        )

        buttons = InlineKeyboardMarkup([[InlineKeyboardButton(text="عرض كامل النص", url=f"https://t.me/{app.username}?start=lyrics_{r_hash}")]])
        await status.edit(f"تمت المعالجة بنجاح.\n\nالعمل: {song.title}\nالفنان: {song.artist}", reply_markup=buttons)
    except Exception:
        await status.edit("حدث خطأ في جلب البيانات.")

@app.on_message(filters.regex(r"^/start lyrics_") & ~BANNED_USERS, group=-1)
async def display_lyrics_handler(client, m: Message):
    try:
        l_hash = m.text.split("lyrics_")[1]
        data = await lyrics_col.find_one({"_id": l_hash})
        if not data: return await m.reply_text("البيانات غير موجودة.")
        
        content = data["c"]
        if len(content) > 4000: content = content[:4000] + "\n\n(تم الاقتطاع للطول الزائد)"
        
        await m.reply_text(f"النص الكامل للطلب:\n\n{content}", disable_web_page_preview=True)
    except Exception: pass
