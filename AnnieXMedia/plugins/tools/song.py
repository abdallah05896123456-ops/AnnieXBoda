# System: Song Plugin | Interactive Fix | Full Maintenance | No Emojis

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

# --- مـتـغـيـرات الـتـحـكـم ---
SEARCH_SECTION_LOCKED = False
INLINE_SEARCH_LOCKED = False

# --- أوامـر الـقـفـل الـعـام (الصيانة) ---

@app.on_message(filters.command(["قفل البحث", "تعطيل البحث"], prefixes=["", "/"]) & filters.user(OWNER_ID))
async def lock_whole_section(client, message):
    global SEARCH_SECTION_LOCKED
    SEARCH_SECTION_LOCKED = True
    await message.reply_text("**تـم قـفـل قـسـم الـبـحـث والـتـحـمـيـل نـهـائـيـاً عـن الـأعـضـاء.**\n\n**يـمـكـنـك فـقـط اسـتـخـدام الـبـوت.**")

@app.on_message(filters.command(["فتح البحث", "تفعيل البحث"], prefixes=["", "/"]) & filters.user(OWNER_ID))
async def unlock_whole_section(client, message):
    global SEARCH_SECTION_LOCKED
    SEARCH_SECTION_LOCKED = False
    await message.reply_text("**تـم فـتـح قـسـم الـبـحـث والـتـحـمـيـل لـلـجـمـيـع.**")

# --- أوامـر قـفـل الانـلايـن ---

@app.on_message(filters.command(["قفل انلاين البحث", "قفل انلاين بحث"], prefixes=["", "/"]) & filters.user(OWNER_ID))
async def lock_inline_search(client, message):
    global INLINE_SEARCH_LOCKED
    INLINE_SEARCH_LOCKED = True
    await message.reply_text("**تـم قـفـل بـحـث الانـلايـن (الأزرار).**\n\n**سـيـتـم الـتـحـمـيـل مـبـاشـرةً عـنـد طـلـب أي أغـنـيـة لـلـجـمـيـع.**")

@app.on_message(filters.command(["فتح انلاين البحث", "فتح انلاين بحث"], prefixes=["", "/"]) & filters.user(OWNER_ID))
async def unlock_inline_search(client, message):
    global INLINE_SEARCH_LOCKED
    INLINE_SEARCH_LOCKED = False
    await message.reply_text("**تـم فـتـح بـحـث الانـلايـن.**\n\n**سـتـظـهـر أزرار اخـتـيـار الـجـودة عـنـد الـطـلـب.**")


# --- الـمـعـالـج الـذكـي الـمـوحـد (Regex) ---
@app.on_message(filters.regex(r"^/?(اغنية|اغنيه|هات|هاتلي|ابعتلي|song|video|تحميل)(?:\s+(فيد|فيديو|video))?(?:\s+(.+))?$") & ~BANNED_USERS)
async def unified_song_processor(client, message: Message):
    
    # 1. فحص القفل العام
    if SEARCH_SECTION_LOCKED and message.from_user.id != OWNER_ID:
        return await message.reply_text("**عـذراً، قـسـم الـبـحـث والـتـحـمـيـل مـغـلـق حـالـيـاً لـلـصـيـانـة.**")

    match = re.match(r"^/?(اغنية|اغنيه|هات|هاتلي|ابعتلي|song|video|تحميل)(?:\s+(فيد|فيديو|video))?(?:\s+(.+))?$", message.text)
    if not match: return
    
    command_trigger = match.group(1).lower()
    video_trigger = match.group(2)
    query = match.group(3)

    is_video_request = False
    if command_trigger in ["video", "/video", "فيديو"] or video_trigger:
        is_video_request = True

    # 2. الـتـفـاعـل (Pyromod) - إصلاح المشكلة هنا
    if not query:
        # إرسال الرسالة أولاً
        prompt = await message.reply_text("**ارسـل الان اسـم الـمـقـطـع الـمـطـلـوب .**")
        
        try:
            # محاولة الاستماع (انتظار 20 ثانية)
            if not hasattr(client, "listen"):
                raise AttributeError("Pyromod not found")

            response = await client.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=20)
            
            if response and response.text:
                query = response.text
                await prompt.delete()
            else:
                await prompt.edit_text("**تـم انـهـاء الانـتـظـار لـعـدم وجـود رد**")
                return

        except asyncio.TimeoutError:
            await prompt.edit_text("**تـم انـهـاء الانـتـظـار لـعـدم وجـود رد**")
            return
        except AttributeError:
            # إذا لم تكن المكتبة موجودة، نطلب الكتابة بجانب الأمر بدلاً من رسالة الخطأ
            await prompt.edit_text("**عـذراً، يـرجـى كـتـابـة الاسـم بـجـانـب الأمـر مـبـاشـرةً.**")
            return
        except Exception:
            await prompt.edit_text("**حـدث خـطـأ، حـاول مـرة أخـرى.**")
            return

    # 3. بدء البحث
    mystic = await message.reply_text("**جـارٍ الـبـحـث عـن الـمـطـلـوب...**")

    try:
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(query)
        if duration_sec is None: duration_sec = 0
        
        # السماح بمدة تصل لـ 4 ساعات (14400 ثانية)
        if int(duration_sec) > 14400:
            return await mystic.edit_text("**عـذراً، هـذا الـمـقـطـع طـويـل جـداً ولا يـمـكـن تـحـمـيـلـه.**")
        
        # --- التحميل المباشر (عند القفل) ---
        if INLINE_SEARCH_LOCKED:
             await mystic.edit_text("**جـارٍ الـتـحـمـيـل الـفـوري...**")
             
             is_owner = (message.from_user.id == OWNER_ID)
             yturl = f"https://www.youtube.com/watch?v={vidid}"
             quality_arg = "high" if is_owner else "mid"

             file_path = await Processor.download_file(
                 yturl, quality_arg, is_video_request, title, vidid=vidid, is_owner=is_owner
             )
             
             await mystic.edit_text("**جـارٍ الـرفـع إلـيـك...**")
             await Processor.upload_alexa_style(
                 client, mystic, file_path, is_video_request, title, duration_sec, message.from_user.first_name, vidid=vidid
             )

        # --- الأزرار (الوضع الطبيعي) ---
        else:
            buttons = song_markup(None, vidid)
            await mystic.delete()
            await message.reply_photo(
                photo=thumbnail, 
                caption=f"**الـعـنـوان:** {title}\n**الـمـدة:** {duration_min}\n\n**اخـتـر الـجـودة والـنـوع الـمـطـلـوب:**",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    except Exception:
        # Fallback
        if INLINE_SEARCH_LOCKED or is_video_request:
            await mystic.edit_text("**جـارٍ الـبـحـث والـتـحـمـيـل الـتـلـقـائـي...**")
            is_owner = (message.from_user.id == OWNER_ID)
            
            file_path = await Processor.download_file(
                query, "mid", is_video_request, query, is_owner=is_owner
            )
            
            if file_path:
                 await mystic.edit_text("**جـارٍ الـرفـع...**")
                 await Processor.upload_alexa_style(
                     client, mystic, file_path, is_video_request, query, 0, message.from_user.first_name
                 )
            else:
                await mystic.edit_text("**عـذراً، لـم يـتـم الـعـثـور عـلـى أي نـتـائـج.**")
        else:
             await mystic.edit_text("**عـذراً، لـم يـتـم الـعـثـور عـلـى نـتـائـج.**")

# --- يـوت (صـوت مـبـاشـر) ---
@app.on_message(filters.command(["يوت"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_direct_audio(client, message: Message):
    if SEARCH_SECTION_LOCKED and message.from_user.id != OWNER_ID:
        return await message.reply_text("**عـذراً، قـسـم الـبـحـث والـتـحـمـيـل مـغـلـق حـالـيـاً لـلـصـيـانـة.**")

    if len(message.command) > 1 and message.command[1] in ["فيد", "فيديو", "video", "vid"]:
        return 

    if len(message.command) < 2:
        return await message.reply_text("**يـرجـى كـتـابـة الـرابـط أو الاسـم.**")
    
    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("**جـارٍ تـحـمـيـل الـصـوت...**")
    
    try:
        title, _, duration_sec, _, vidid = await YouTube.details(query)
        if duration_sec is None: duration_sec = 0
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        
        is_owner = (message.from_user.id == OWNER_ID)
        quality_arg = "high" if is_owner else "mid"

        file_path = await Processor.download_file(
            yturl, quality_arg, False, title, vidid=vidid, is_owner=is_owner
        )
        
        await mystic.edit_text("**جـارٍ الـرفـع...**")
        await Processor.upload_alexa_style(
            client, mystic, file_path, False, title, duration_sec, message.from_user.first_name, vidid=vidid
        )
    except Exception as e:
        await mystic.edit_text(f"**حـدث خـطـأ:** {e}")

# --- يـوت فـيـد (فـيـديـو مـبـاشـر) ---
@app.on_message(filters.command(["يوت فيد", "يوت فيديو"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_direct_video(client, message: Message):
    if SEARCH_SECTION_LOCKED and message.from_user.id != OWNER_ID:
        return await message.reply_text("**عـذراً، قـسـم الـبـحـث والـتـحـمـيـل مـغـلـق حـالـيـاً لـلـصـيـانـة.**")

    if len(message.command) < 3: 
        return await message.reply_text("**يـرجـى كـتـابـة اسـم الـفـيـديـو.**")
    
    query = message.text.split(None, 2)[2]
    mystic = await message.reply_text("**جـارٍ تـحـمـيـل الـفـيـديـو...**")
    
    try:
        title, _, duration_sec, _, vidid = await YouTube.details(query)
        if duration_sec is None: duration_sec = 0
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        
        is_owner = (message.from_user.id == OWNER_ID)
        quality_arg = "high" if is_owner else "mid"

        file_path = await Processor.download_file(
            yturl, quality_arg, True, title, vidid=vidid, is_owner=is_owner
        )
        
        await mystic.edit_text("**جـارٍ الـرفـع...**")
        await Processor.upload_alexa_style(
            client, mystic, file_path, True, title, duration_sec, message.from_user.first_name, vidid=vidid
        )
    except Exception as e:
        await mystic.edit_text(f"**حـدث خـطـأ:** {e}")


# --- مـعـالـجـة الأزرار ---
@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
async def song_download_callback(client, CallbackQuery):
    if SEARCH_SECTION_LOCKED and CallbackQuery.from_user.id != OWNER_ID:
        return await CallbackQuery.answer("⚠️ قـسـم الـتـحـمـيـل مـغـلـق لـلـصـيـانـة.", show_alert=True)

    if INLINE_SEARCH_LOCKED and CallbackQuery.from_user.id != OWNER_ID:
         return await CallbackQuery.answer("تـم قـفـل الـتـحـمـيـل عـبـر الأزرار حـالـيـاً.", show_alert=True)

    stype, quality_arg, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جـارٍ بـدء الـعـمـلـيـة...")
    
    mystic = await CallbackQuery.message.edit_text("**جـارٍ الـتـحـمـيـل...**")
    
    is_video = (stype == "video")
    is_owner = (CallbackQuery.from_user.id == OWNER_ID)
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    
    try:
        title, _, duration_sec, _, _ = await YouTube.details(vidid)
        if duration_sec is None: duration_sec = 0

        file_path = await Processor.download_file(
            yturl, quality_arg, is_video, title, vidid=vidid, is_owner=is_owner
        )
        
        await mystic.edit_text("**جـارٍ الـرفـع...**")
        await Processor.upload_alexa_style(
            client, mystic, file_path, is_video, title, duration_sec, CallbackQuery.from_user.first_name, vidid=vidid
        )

    except Exception:
        await mystic.edit_text("**فـشـل الـتـحـمـيـل.**")

@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS)
async def song_helper_callback(client, CallbackQuery):
    if SEARCH_SECTION_LOCKED and CallbackQuery.from_user.id != OWNER_ID:
        return await CallbackQuery.answer("⚠️ قـسـم الـتـحـمـيـل مـغـلـق لـلـصـيـانـة.", show_alert=True)

    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جـارٍ جـلـب الـخـيـارات...")
    buttons = await Processor.get_quality_buttons(vidid, stype)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS)
async def song_back_callback(client, CallbackQuery):
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    buttons = song_markup(None, vidid)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
