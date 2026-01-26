# System: Song Plugin with Direct Mode Toggle & Smart Regex

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
# False = الأزرار تعمل (الوضع الطبيعي)
# True = التحميل مباشر (وضع القفل)
INLINE_SEARCH_LOCKED = False

# --- أوامر التحكم للمطور ---

@app.on_message(filters.command(["قفل انلاين البحث", "قفل انلاين بحث"], prefixes=["", "/"]) & filters.user(OWNER_ID))
async def lock_inline_search(client, message):
    global INLINE_SEARCH_LOCKED
    INLINE_SEARCH_LOCKED = True
    await message.reply_text("**تم قفل بحث الانلاين (الأزرار).**\n\n**سيتم التحميل مباشرةً عند طلب أي أغنية للجميع.**")

@app.on_message(filters.command(["فتح انلاين البحث", "فتح انلاين بحث"], prefixes=["", "/"]) & filters.user(OWNER_ID))
async def unlock_inline_search(client, message):
    global INLINE_SEARCH_LOCKED
    INLINE_SEARCH_LOCKED = False
    await message.reply_text("**تم فتح بحث الانلاين.**\n\n**ستظهر أزرار اختيار الجودة عند الطلب.**")

# --- المعالج الذكي الموحد (Regex) ---
# يلتقط: (اغنية/هات/song...) + (فيد/فيديو اختياري) + (الاسم)
@app.on_message(filters.regex(r"^/?(اغنية|اغنيه|هات|ابعتلي|song|video)(?:\s+(فيد|فيديو|video))?\s+(.+)") & ~BANNED_USERS)
async def unified_song_processor(client, message: Message):
    
    match = re.match(r"^/?(اغنية|اغنيه|هات|ابعتلي|song|video)(?:\s+(فيد|فيديو|video))?\s+(.+)", message.text)
    if not match: return
    
    command_trigger = match.group(1).lower()
    video_trigger = match.group(2)
    query = match.group(3)

    # تحديد هل الطلب فيديو؟
    is_video_request = False
    if command_trigger in ["video", "/video"] or video_trigger:
        is_video_request = True

    mystic = await message.reply_text("**جاري البحث عن المطلوب...**")

    try:
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(query)
        
        # معالجة الخطأ إذا كانت المدة غير معروفة
        if duration_sec is None: duration_sec = 0
        
        if int(duration_sec) > SONG_DOWNLOAD_DURATION_LIMIT:
            return await mystic.edit_text("**عذراً، هذا المقطع طويل جداً ولا يمكن تحميله.**")
        
        # فحص وضع القفل
        if INLINE_SEARCH_LOCKED:
             await mystic.edit_text("**جاري التحميل الفوري...**")
             
             is_owner = (message.from_user.id == OWNER_ID)
             yturl = f"https://www.youtube.com/watch?v={vidid}"
             
             # نرسل "best" أو "bestaudio" والمعالج سيحدد الجودة حسب الرتبة
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
             
             thumb_file = await message.download_media(thumbnail) if thumbnail else None
             
             success = await Processor.send_smart_file(
                 client, 
                 message.chat.id, 
                 file_path, 
                 is_video_request, 
                 title, 
                 duration_sec, 
                 thumb_file, 
                 message.from_user.first_name
             )
             
             if success:
                 await mystic.delete()
                 if thumb_file and os.path.exists(thumb_file): os.remove(thumb_file)
             else:
                 await mystic.edit_text("**حدث خطأ أثناء الرفع.**")

        # الوضع الطبيعي (الأزرار)
        else:
            buttons = song_markup(None, vidid)
            await mystic.delete()
            await message.reply_photo(
                photo=thumbnail, 
                caption=f"**العنوان:** {title}\n**المدة:** {duration_min}\n\n**اختر الجودة والنوع المطلوب:**",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    except Exception:
        await mystic.edit_text("**لم يتم العثور على نتائج.**")

# --- أمر يوت (تحميل صوت مباشر) ---
@app.on_message(filters.command(["يوت"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_direct_processor(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("**يرجى كتابة الرابط أو الاسم بعد الأمر.**")
    
    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("**جاري التحميل...**")
    
    try:
        title, _, duration_sec, _, vidid = await YouTube.details(query)
        if duration_sec is None: duration_sec = 0
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        
        is_owner = (message.from_user.id == OWNER_ID)
        
        file_path = await Processor.download_file(
            yturl, "bestaudio", False, title, vidid=vidid, is_owner=is_owner
        )
        
        await mystic.edit_text("**جاري الرفع...**")
        await Processor.send_smart_file(
            client, message.chat.id, file_path, False, 
            title, duration_sec, None, message.from_user.first_name
        )
        await mystic.delete()
    except Exception as e:
        await mystic.edit_text(f"**حدث خطأ:** {e}")

# --- أمر يوت فيد (تحميل فيديو مباشر) ---
@app.on_message(filters.command(["يوت فيد"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_vid_direct_processor(client, message: Message):
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
        await Processor.send_smart_file(
            client, message.chat.id, file_path, True, 
            title, duration_sec, None, message.from_user.first_name
        )
        await mystic.delete()
    except Exception as e:
        await mystic.edit_text(f"**حدث خطأ:** {e}")


# --- معالجة الأزرار ---
@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
async def song_download_callback(client, CallbackQuery):
    # منع التحميل من الأزرار القديمة إذا تم تفعيل القفل
    if INLINE_SEARCH_LOCKED and CallbackQuery.from_user.id != OWNER_ID:
         return await CallbackQuery.answer("تم قفل التحميل عبر الأزرار حالياً.", show_alert=True)

    stype, quality_arg, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جاري بدء العملية...")
    mystic = await CallbackQuery.edit_message_text("**جاري التحميل...**")
    
    is_video = (stype == "video")
    is_owner = (CallbackQuery.from_user.id == OWNER_ID)
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    
    try:
        title, _, duration_sec, _, _ = await YouTube.details(vidid)
        if duration_sec is None: duration_sec = 0

        file_path = await Processor.download_file(
            yturl, 
            quality_arg, 
            is_video, 
            title, 
            vidid=vidid, 
            is_owner=is_owner
        )
        
        thumb = await CallbackQuery.message.download() if CallbackQuery.message.photo else None
        
        await mystic.edit_text("**جاري الرفع...**")
        
        if is_video:
            media = InputMediaVideo(
                media=file_path, thumb=thumb, caption=f"{title}", 
                duration=duration_sec, supports_streaming=True
            )
        else:
            media = InputMediaAudio(
                media=file_path, thumb=thumb, caption=f"{title}", 
                duration=duration_sec, title=title, performer=CallbackQuery.from_user.first_name
            )
        
        try:
            await CallbackQuery.edit_message_media(media=media)
        except Exception:
            await Processor.send_smart_file(
                client, CallbackQuery.message.chat.id, file_path, 
                is_video, title, duration_sec, thumb, CallbackQuery.from_user.first_name
            )
        
        await mystic.delete()
        if thumb and os.path.exists(thumb): os.remove(thumb)

    except Exception:
        await mystic.edit_text("**فشل التحميل، حاول مرة أخرى.**")

@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS)
async def song_helper_callback(client, CallbackQuery):
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جاري جلب الخيارات...")
    buttons = await Processor.get_quality_buttons(vidid, stype)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS)
async def song_back_callback(client, CallbackQuery):
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    buttons = song_markup(None, vidid)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
