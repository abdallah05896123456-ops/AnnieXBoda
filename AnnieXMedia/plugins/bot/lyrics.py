# Authored By Certified Coders 2026
# LYRICS SYSTEM - MONGODB PERMANENT EDITION
# Optimized for AnnieXMedia | No Emojis | Detailed Logic

import asyncio
import random
import re
import string
import time
import lyricsgenius as lg
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from motor.motor_asyncio import AsyncIOMotorClient

from AnnieXMedia import app
import config
from config import BANNED_USERS, MONGO_DB_URI

# الاتصال بقاعدة البيانات لضمان حفظ الكلمات بشكل دائم
mongo_client = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo_client.Annie
lyrics_col = db.lyrics_cache

# الكود المستخرج من بياناتك (Client Access Token)
GENIUS_API_KEY = "WbhEqtER5NoCKr50VdOFyhk6Rtwgk-lVenk_E3iKmADpADtzDB19oU8wZA5pcDbVzt4l9g_G7Ft8uEdX4ecLvw"

genius_engine = lg.Genius(
    GENIUS_API_KEY, 
    skip_non_songs=True, 
    remove_section_headers=True
)
genius_engine.verbose = False
genius_engine.timeout = 20

SUDO_USERS = config.OWNER_ID if isinstance(config.OWNER_ID, list) else [config.OWNER_ID]
LYRICS_STATUS = True

def clean_lyrics(raw):
    if not raw: return ""
    p = re.sub(r"^.*?Lyrics", "", raw, flags=re.DOTALL)
    p = p.replace("You might also like", "")
    p = re.sub(r"\d*Embed", "", p)
    p = re.sub(r"[0-9]+$", "", p)
    return p.strip()

@app.on_message(filters.regex(r"^(قفل الكلمات|فتح الكلمات)$") & filters.user(SUDO_USERS))
async def lyrics_management_switch(_, m: Message):
    global LYRICS_STATUS
    LYRICS_STATUS = "فتح" in m.text
    await m.reply_text(f"لقد تم {'تفعيل' if LYRICS_STATUS else 'تعطيل'} نظام البحث عن الكلمات بشكل رسمي من قبل الادارة.")

@app.on_message(filters.regex(r"^(كلمات )") & ~BANNED_USERS)
async def lyrics_search_engine(client, m: Message):
    if not LYRICS_STATUS and m.from_user.id not in SUDO_USERS:
        return await m.reply_text("نعتذر منك ولكن هذا القسم مغلق حاليا بقرار من مبرمج البوت.")

    try:
        query = m.text.split(None, 1)[1].strip()
    except IndexError:
        return await m.reply_text("يرجى كتابة اسم الاغنية المطلوب البحث عنها لكي يبدأ النظام في العمل.")
        
    status = await m.reply_text("جاري البدء في عملية البحث داخل قاعدة البيانات العالمية يرجى الانتظار قليلا.")
    
    try:
        loop = asyncio.get_event_loop()
        song = await loop.run_in_executor(None, lambda: genius_engine.search_song(query))
        
        if not song or not song.lyrics:
            return await status.edit(f"لم يتم العثور على اي نتائج تطابق بحثك عن {query} يرجى التأكد من الاسم.")

        final_lyrics = clean_lyrics(song.lyrics)
        r_hash = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
        
        # حفظ دائم في MongoDB
        await lyrics_col.update_one(
            {"_id": r_hash},
            {"$set": {"t": song.title, "a": song.artist, "c": final_lyrics, "d": time.time()}},
            upsert=True
        )

        upl = InlineKeyboardMarkup([[InlineKeyboardButton(text="عرض نص الكلمات بالكامل", url=f"https://t.me/{app.username}?start=lyrics_{r_hash}")]])
        await status.edit(f"لقد تم الانتهاء من عملية البحث بنجاح واستخراج الكلمات.\n\nاسم العمل: {song.title}\nاسم الفنان: {song.artist}", reply_markup=upl)
    except Exception as e:
        await status.edit("حدث خطأ غير متوقع اثناء الاتصال بخوادم قاعدة البيانات العالمية يرجى المحاولة لاحقا.")

@app.on_message(filters.regex(r"^/start lyrics_") & ~BANNED_USERS, group=-1)
async def display_lyrics_handler(client, m: Message):
    try:
        l_hash = m.text.split("lyrics_")[1]
        data = await lyrics_col.find_one({"_id": l_hash})
        if not data: return await m.reply_text("لم يتم العثور على الكلمات المطلوبة في السجلات.")
        
        content = data["c"]
        if len(content) > 4000: content = content[:4000] + "\n\n(تم اقتطاع النص نظرا لطوله الزائد)."
        
        await m.reply_text(f"إليك الكلمات الكاملة للعمل الفني الذي بحثت عنه:\n\n{content}", disable_web_page_preview=True)
        m.stop_propagation()
    except: pass
