# Authored By Certified Coders © 2026
# LYRICS SYSTEM - AnnieXMedia SOURCE
# High Performance Lyrics Search & Formatting

import asyncio
import random
import re
import string
import lyricsgenius as lg
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from AnnieXMedia import app
from config import BANNED_USERS, lyrical

# ==========================================
# إعدادات المحرك والاتصال
# ==========================================

GENIUS_API_KEY = "Hqw2MvfHddbZcv_5q3PsFYt_q_tAnGirPUlzxfJKU04vy-URdIopznmh2Z-jLaueU1YkGLahD2rNCTZq4TVVEQ"

# تهيئة كائن Genius مع إعدادات تقليل الضوضاء في النص
genius_engine = lg.Genius(
    GENIUS_API_KEY, 
    skip_non_songs=True, 
    excluded_terms=["(Remix)", "(Live)"], 
    remove_section_headers=True
)
genius_engine.verbose = False

# تحسين رؤوس الطلبات لتجنب الحظر من Genius
genius_engine._session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
})

# ==========================================
# دالات المعالجة والتنظيف
# ==========================================

def clean_lyrics_text(raw_lyrics):
    """تنظيف نصوص كلمات الأغاني من مخلفات API جينيوس"""
    if not raw_lyrics:
        return ""
    
    # 1. إزالة الديباجة (Contributors ... Lyrics)
    processed = re.sub(r"^.*?Lyrics", "", raw_lyrics, flags=re.DOTALL)
    
    # 2. إزالة الكلمات التسويقية والروابط
    processed = processed.replace("You might also like", "")
    
    # 3. إزالة بصمة Embed والأرقام البرمجية في نهاية النص
    processed = re.sub(r"\d*Embed", "", processed)
    
    # 4. إزالة أي فراغات زائدة في البداية والنهاية
    return processed.strip()

# ==========================================
# معالج البحث (أمر: كلمات) - بدون بادئة
# ==========================================

@app.on_message(filters.regex(r"^(كلمات)$") & ~BANNED_USERS)
async def lyrics_usage_hint(_, message: Message):
    await message.reply_text("يـجـب كـتـابة اسـم الاغـنـيـة بـعـد الامـر. مـثـال: كلمات الاسم")

@app.on_message(filters.regex(r"^(كلمات )") & ~BANNED_USERS)
async def lyrics_search_handler(client, message: Message):
    # استخراج اسم الأغنية من النص
    search_query = message.text.split(None, 1)[1].strip()
    
    status_msg = await message.reply_text("جـاري الـبـحث عـن كـلـمات الاغـنـيـة في قـاعـدة البيانات")
    
    try:
        # البحث عن الأغنية (عملية blocking لذلك نستخدم run_in_executor)
        loop = asyncio.get_event_loop()
        song_data = await loop.run_in_executor(None, genius_engine.search_song, search_query)
        
        if not song_data:
            return await status_msg.edit(f"لـم يـتم الـعـثـور عـلى كـلمات لـ: {search_query}")

        # تنظيف الكلمات وحفظها في الرام
        final_lyrics = clean_lyrics_text(song_data.lyrics)
        random_hash = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
        lyrical[random_hash] = final_lyrics

        # إنشاء زر العرض
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(text="عـرض الـكـلـمـات", url=f"https://t.me/{app.username}?start=lyrics_{random_hash}")]
        ])
        
        await status_msg.edit(
            f"تـم الـعـثـور عـلى كـلـمات الاغـنـيـة\n\nالاغـنـيـة: {song_data.title}\nالـفـنان: {song_data.artist}\nالـمـصـدر: Genius",
            reply_markup=buttons
        )
    
    except Exception as error:
        print(f"Lyrics Engine Error: {error}")
        await status_msg.edit("حـدث خـطأ غـير مـتوقع أثـناء جـلب الـكلمات")

# ==========================================
# معالج العرض (Deep Link Handler)
# ==========================================

@app.on_message(filters.regex(r"^/start lyrics_") & ~BANNED_USERS, group=-1)
async def lyrics_display_handler(client, message: Message):
    try:
        # استخراج الهاش من الرابط
        lyrics_hash = message.text.split("lyrics_")[1]
        content = lyrical.get(lyrics_hash)
        
        if not content:
            return await message.reply_text("عـذراً، انـتـهت صـلاحـية هـذا الـرابط. يـرجى الـبـحث مـرة أخـرى")
        
        # تقسيم النص إذا كان طويلاً جداً (حدود تيليجرام 4096 حرف)
        if len(content) > 4000:
            content = content[:4000] + "\n\n(تـم اقـتـطـاع الـنـص لـطـولـه الـزائد)"
            
        await message.reply_text(
            f"كـلـمـات الاغـنـيـة:\n\n{content}",
            disable_web_page_preview=True
        )
        
        # منع معالجة الأمر في أماكن أخرى
        message.stop_propagation()
        
    except Exception as display_error:
        print(f"Lyrics Display Error: {display_error}")

# ==========================================
# نـهـايـة مـلـف الـكـلـمـات - AnnieXMedia
# ==========================================
