# System: Song Plugin | Video Detection Fix | Direct Upload

import asyncio
import os
import re
from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup, 
    Message, 
    InputMediaAudio, 
    InputMediaVideo
)

from config import BANNED_USERS, SONG_DOWNLOAD_DURATION, SONG_DOWNLOAD_DURATION_LIMIT, OWNER_ID
from AnnieXMedia import app
from AnnieXMedia.platforms.Youtube import YouTube 
from AnnieXMedia.platforms.YTProcessor import Processor 
from AnnieXMedia.utils.inline.song import song_markup

# متغير التحكم في وضع البحث (الأزرار)
INLINE_SEARCH_LOCKED = False

# --- أوامر التحكم للمطور ---

@app.on_message(filters.command(["قفل انلاين البحث", "قفل انلاين بحث"], prefixes=["", "/"]) & filters.user(OWNER_ID))
async def lock_inline_search(client, message):
    global INLINE_SEARCH_LOCKED
    INLINE_SEARCH_LOCKED = True
    await message.reply_text("**تم قفل بحث الانلاين (الأزرار). سيتم التحميل المباشر للجميع.**")

@app.on_message(filters.command(["فتح انلاين البحث", "فتح انلاين بحث"], prefixes=["", "/"]) & filters.user(OWNER_ID))
async def unlock_inline_search(client, message):
    global INLINE_SEARCH_LOCKED
    INLINE_SEARCH_LOCKED = False
    await message.reply_text("**تم فتح بحث الانلاين.**")

# --- المعالج الذكي الموحد (Regex) ---
# يلتقط الأوامر المركبة مثل: هات فيديو، اغنية فيد، ابعتلي فيديو...
@app.on_message(filters.regex(r"^/?(اغنية|اغنيه|هات|ابعتلي|song|video|تحميل)(?:\s+(فيد|فيديو|video))?\s+(.+)") & ~BANNED_USERS)
async def unified_song_processor(client, message: Message):
    
    match = re.match(r"^/?(اغنية|اغنيه|هات|ابعتلي|song|video|تحميل)(?:\s+(فيد|فيديو|video))?\s+(.+)", message.text)
    if not match: return
    
    command_trigger = match.group(1).lower() # الكلمة الأولى (مثل: هات)
    video_trigger = match.group(2) # الكلمة الثانية (مثل: فيديو) - قد تكون None
    query = match.group(3) # اسم البحث

    # تحديد نوع الطلب بدقة
    is_video_request = False
    if command_trigger in ["video", "/video", "فيديو"] or video_trigger:
        is_video_request = True

    mystic = await message.reply_text("**جاري البحث...**")

    try:
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(query)
        if duration_sec is None: duration_sec = 0
        
        if int(duration_sec) > SONG_DOWNLOAD_DURATION_LIMIT:
            return await mystic.edit_text("**عذراً، هذا المقطع طويل جداً ولا يمكن تحميله.**")
        
        # إذا كان البحث الانلاين مقفولاً (وضع التحميل المباشر)
        if INLINE_SEARCH_LOCKED:
             await mystic.edit_text("**جاري التحميل الفوري...**")
             
             is_owner = (message.from_user.id == OWNER_ID)
             yturl = f"https://www.youtube.com/watch?v={vidid}"
             
             # إذا كان فيديو: نطلب best، إذا صوت: bestaudio
             quality_arg = "best" if is_video_request else "bestaudio"

             file_path = await Processor.download_file(
                 yturl, 
                 quality_arg, 
                 is_video_request, 
                 title, 
                 vidid=vidid, 
                 is_owner=is_owner
             )
             
             await mystic.edit_text("**جاري الرفع إليك...**")
             
             await Processor.upload_alexa_style(
                 client, 
                 mystic, 
                 file_path, 
                 is_video_request, 
                 title, 
                 duration_sec, 
                 message.from_user.first_name, 
                 vidid=vidid
             )

        # الوضع الطبيعي (إظهار الأزرار)
        else:
            buttons = song_markup(None, vidid)
            await mystic.delete()
            await message.reply_photo(
                photo=thumbnail, 
                caption=f"**العنوان:** {title}\n**المدة:** {duration_min}\n\n**اختر الجودة والنوع المطلوب:**",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    except Exception:
        # المحاولة الثانية (Fallback) في حال فشل جلب التفاصيل
        if INLINE_SEARCH_LOCKED or is_video_request:
            await mystic.edit_text("**جاري البحث والتحميل التلقائي...**")
            is_owner = (message.from_user.id == OWNER_ID)
            
            # نرسل اسم البحث مباشرة للمعالج
            file_path = await Processor.download_file(
                query, 
                "best" if is_video_request else "bestaudio", 
                is_video_request, 
                query, 
                is_owner=is_owner
            )
            
            if file_path:
                 await mystic.edit_text("**جاري الرفع...**")
                 await Processor.upload_alexa_style(
                     client, 
                     mystic, 
                     file_path, 
                     is_video_request, 
                     query, 
                     0, 
                     message.from_user.first_name
                 )
            else:
                await mystic.edit_text("**عذراً، لم يتم العثور على نتائج.**")
        else:
             await mystic.edit_text("**عذراً، لم يتم العثور على نتائج.**")

# --- أمر يوت (صوت مباشر) ---
@app.on_message(filters.command(["يوت"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_direct_audio(client, message: Message):
    # نتأكد أنه ليس "يوت فيد"
    if len(message.command) > 1 and message.command[1] in ["فيد", "فيديو", "video", "vid"]:
        return # نترك المعالجة للدالة التالية

    if len(message.command) < 2:
        return await message.reply_text("**يرجى كتابة الرابط أو الاسم.**")
    
    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("**جاري تحميل الصوت...**")
    
    try:
        title, _, duration_sec, _, vidid = await YouTube.details(query)
        if duration_sec is None: duration_sec = 0
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        
        is_owner = (message.from_user.id == OWNER_ID)
        
        file_path = await Processor.download_file(
            yturl, "bestaudio", False, title, vidid=vidid, is_owner=is_owner
        )
        
        await mystic.edit_text("**جاري الرفع...**")
        await Processor.upload_alexa_style(
            client, mystic, file_path, False, title, duration_sec, message.from_user.first_name, vidid=vidid
        )
    except Exception as e:
        await mystic.edit_text(f"**حدث خطأ:** {e}")

# --- أمر يوت فيد (فيديو مباشر) ---
@app.on_message(filters.command(["يوت فيد", "يوت فيديو"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_direct_video(client, message: Message):
    if len(message.command) < 3: 
        return await message.reply_text("**يرجى كتابة اسم الفيديو.**")
    
    query = message.text.split(None, 2)[2]
    mystic = await message.reply_text("**جاري تحميل الفيديو...**")
    
    try:
        title, _, duration_sec, _, vidid = await YouTube.details(query)
        if duration_sec is None: duration_sec = 0
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        
        is_owner = (message.from_user.id == OWNER_ID)
        
        file_path = await Processor.download_file(
            yturl, "best", True, title, vidid=vidid, is_owner=is_owner
        )
        
        await mystic.edit_text("**جاري الرفع...**")
        await Processor.upload_alexa_style(
            client, mystic, file_path, True, title, duration_sec, message.from_user.first_name, vidid=vidid
        )
    except Exception as e:
        await mystic.edit_text(f"**حدث خطأ:** {e}")


# --- معالجة الأزرار ---
@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
async def song_download_callback(client, CallbackQuery):
    if INLINE_SEARCH_LOCKED and CallbackQuery.from_user.id != OWNER_ID:
         return await CallbackQuery.answer("تم قفل التحميل عبر الأزرار حالياً.", show_alert=True)

    stype, quality_arg, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جاري بدء العملية...")
    
    mystic = await CallbackQuery.message.edit_text("**جاري التحميل...**")
    
    is_video = (stype == "video")
    is_owner = (CallbackQuery.from_user.id == OWNER_ID)
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    
    try:
        title, _, duration_sec, _, _ = await YouTube.details(vidid)
        if duration_sec is None: duration_sec = 0

        file_path = await Processor.download_file(
            yturl, quality_arg, is_video, title, vidid=vidid, is_owner=is_owner
        )
        
        await mystic.edit_text("**جاري الرفع...**")
        
        await Processor.upload_alexa_style(
            client, mystic, file_path, is_video, title, duration_sec, CallbackQuery.from_user.first_name, vidid=vidid
        )

    except Exception:
        await mystic.edit_text("**فشل التحميل.**")

@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS)
async def song_helper_callback(client, CallbackQuery):
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
