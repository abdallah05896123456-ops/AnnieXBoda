# System: Song Plugin | Playlist Support | MongoDB Fixed | Pyromod

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
from motor.motor_asyncio import AsyncIOMotorClient

# استيراد المتغيرات الأساسية
from config import BANNED_USERS, SONG_DOWNLOAD_DURATION, SONG_DOWNLOAD_DURATION_LIMIT, OWNER_ID, MONGO_DB_URI
from AnnieXMedia import app
from AnnieXMedia.platforms.Youtube import YouTube 
from AnnieXMedia.platforms.YTProcessor import Processor 
from AnnieXMedia.utils.inline.song import song_markup

# --- الاتـصـال بـقـاعـدة الـبـيـانـات ---
_mongo_client_ = AsyncIOMotorClient(MONGO_DB_URI)
mongodb = _mongo_client_.Annie
songdb = mongodb.song_settings

# --- دوال الـتـعـامـل مـع الـقـاعـدة ---
async def get_config(key):
    try:
        data = await songdb.find_one({"_id": "song_config"})
        if not data: return False
        return data.get(key, False)
    except: return False

async def set_config(key, value):
    try:
        await songdb.update_one({"_id": "song_config"}, {"$set": {key: value}}, upsert=True)
    except: pass

# --- أوامـر الـقـفـل الـعـام ---

@app.on_message(filters.command(["قفل البحث", "تعطيل البحث"], prefixes=["", "/"]) & filters.user(OWNER_ID))
async def lock_whole_section(client, message):
    await set_config("search_locked", True)
    await message.reply_text("**تـم قـفـل قـسـم الـبـحـث والـتـحـمـيـل نـهـائـيـاً عـن الـأعـضـاء.**")

@app.on_message(filters.command(["فتح البحث", "تفعيل البحث"], prefixes=["", "/"]) & filters.user(OWNER_ID))
async def unlock_whole_section(client, message):
    await set_config("search_locked", False)
    await message.reply_text("**تـم فـتـح قـسـم الـبـحـث والـتـحـمـيـل لـلـجـمـيـع.**")

# --- أوامـر قـفـل الانـلايـن ---

@app.on_message(filters.command(["قفل انلاين البحث", "قفل انلاين بحث"], prefixes=["", "/"]) & filters.user(OWNER_ID))
async def lock_inline_search(client, message):
    await set_config("inline_locked", True)
    await message.reply_text("**تـم قـفـل بـحـث الانـلايـن (الأزرار).**")

@app.on_message(filters.command(["فتح انلاين البحث", "فتح انلاين بحث"], prefixes=["", "/"]) & filters.user(OWNER_ID))
async def unlock_inline_search(client, message):
    await set_config("inline_locked", False)
    await message.reply_text("**تـم فـتـح بـحـث الانـلايـن.**")


# --- الـمـعـالـج الـذكـي الـمـوحـد (Regex) ---
@app.on_message(filters.regex(r"^/?(اغنية|اغنيه|هات|هاتلي|ابعتلي|song|video|تحميل|play)(?:\s+(فيد|فيديو|video))?(?:\s+(.+))?$") & ~BANNED_USERS)
async def unified_song_processor(client, message: Message):
    
    # 1. فحص القفل
    is_search_locked = await get_config("search_locked")
    if is_search_locked and message.from_user.id != OWNER_ID:
        return await message.reply_text("**عـذراً، قـسـم الـبـحـث والـتـحـمـيـل مـغـلـق حـالـيـاً لـلـصـيـانـة.**")

    match = re.match(r"^/?(اغنية|اغنيه|هات|هاتلي|ابعتلي|song|video|تحميل|play)(?:\s+(فيد|فيديو|video))?(?:\s+(.+))?$", message.text)
    if not match: return
    
    command_trigger = match.group(1).lower()
    video_trigger = match.group(2)
    query = match.group(3)

    is_video_request = False
    if command_trigger in ["video", "/video", "فيديو"] or video_trigger:
        is_video_request = True

    # 2. التفاعل (Pyromod)
    if not query:
        prompt = await message.reply_text("**ارسـل الان اسـم الـمـقـطـع أو رابـط الـقـائـمـة.**")
        try:
            if not hasattr(client, "listen"):
                await prompt.edit_text("**عـذراً، يـرجـى كـتـابـة الـطـلـب بـجـانـب الأمـر.**")
                return
            response = await client.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=20)
            if response and response.text:
                query = response.text
                await prompt.delete()
            else:
                await prompt.edit_text("**تـم انـهـاء الانـتـظـار.**")
                return
        except:
            await prompt.edit_text("**حـدث خـطـأ.**")
            return

    mystic = await message.reply_text("**جـارٍ الـمـعـالـجـة...**")

    # --- 3. اكـتـشـاف الـبـلاي لـيـسـت (Playlist Detection) ---
    # إذا كان الرابط يحتوي على list= فهو قائمة تشغيل
    if "list=" in query and ("youtube.com" in query or "youtu.be" in query):
        try:
            await Processor.download_playlist(
                client=client, 
                mystic_msg=mystic, 
                playlist_url=query, 
                is_video=is_video_request, 
                user_name=message.from_user.first_name
            )
        except Exception as e:
            await mystic.edit_text(f"**حـدث خـطـأ فـي الـقـائـمـة:** {e}")
        return # نخرج من الدالة هنا لأننا انتهينا

    # --- 4. مـعـالـجـة الـفـيـديـو الـفـردي ---
    try:
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(query)
        if duration_sec is None: duration_sec = 0
        
        if int(duration_sec) > 14400:
            return await mystic.edit_text("**عـذراً، الـمـقـطـع طـويـل جـداً.**")
        
        is_inline_locked = await get_config("inline_locked")

        # التحميل المباشر
        if is_inline_locked:
             await mystic.edit_text("**جـارٍ الـتـحـمـيـل الـفـوري...**")
             is_owner = (message.from_user.id == OWNER_ID)
             yturl = f"https://www.youtube.com/watch?v={vidid}"
             quality_arg = "high" if is_owner else "mid"

             file_path = await Processor.download_file(yturl, quality_arg, is_video_request, title, vidid=vidid, is_owner=is_owner)
             
             await mystic.edit_text("**جـارٍ الـرفـع...**")
             await Processor.upload_alexa_style(client, mystic, file_path, is_video_request, title, duration_sec, message.from_user.first_name, vidid=vidid)

        # الأزرار
        else:
            buttons = song_markup(None, vidid)
            await mystic.delete()
            await message.reply_photo(
                photo=thumbnail, 
                caption=f"**الـعـنـوان:** {title}\n**الـمـدة:** {duration_min}\n\n**اخـتـر الـجـودة والـنـوع:**",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    except Exception:
        # Fallback Search
        is_inline_locked = await get_config("inline_locked")
        if is_inline_locked or is_video_request:
            await mystic.edit_text("**جـارٍ الـبـحـث والـتـحـمـيـل...**")
            is_owner = (message.from_user.id == OWNER_ID)
            
            file_path = await Processor.download_file(query, "mid", is_video_request, query, is_owner=is_owner)
            
            if file_path:
                 await mystic.edit_text("**جـارٍ الـرفـع...**")
                 await Processor.upload_alexa_style(client, mystic, file_path, is_video_request, query, 0, message.from_user.first_name)
            else:
                await mystic.edit_text("**عـذراً، لـم يـتـم الـعـثـور عـلـى نـتـائـج.**")
        else:
             await mystic.edit_text("**عـذراً، لـم يـتـم الـعـثـور عـلـى نـتـائـج.**")

# --- يـوت (صـوت مـبـاشـر) ---
@app.on_message(filters.command(["يوت"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_direct_audio(client, message: Message):
    is_search_locked = await get_config("search_locked")
    if is_search_locked and message.from_user.id != OWNER_ID:
        return await message.reply_text("**عـذراً، الـقـسـم مـغـلـق.**")

    if len(message.command) > 1 and message.command[1] in ["فيد", "فيديو", "video", "vid"]:
        return 

    if len(message.command) < 2:
        return await message.reply_text("**يـرجـى كـتـابـة الـرابـط.**")
    
    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("**جـارٍ الـتـحـمـيـل...**")
    
    # دعم البلاي ليست في أمر يوت أيضاً
    if "list=" in query:
         return await Processor.download_playlist(client, mystic, query, False, message.from_user.first_name)

    try:
        title, _, duration_sec, _, vidid = await YouTube.details(query)
        if duration_sec is None: duration_sec = 0
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        
        is_owner = (message.from_user.id == OWNER_ID)
        quality_arg = "high" if is_owner else "mid"

        file_path = await Processor.download_file(yturl, quality_arg, False, title, vidid=vidid, is_owner=is_owner)
        
        await mystic.edit_text("**جـارٍ الـرفـع...**")
        await Processor.upload_alexa_style(client, mystic, file_path, False, title, duration_sec, message.from_user.first_name, vidid=vidid)
    except Exception as e:
        await mystic.edit_text(f"**حـدث خـطـأ:** {e}")

# --- يـوت فـيـد (فـيـديـو مـبـاشـر) ---
@app.on_message(filters.command(["يوت فيد", "يوت فيديو"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_direct_video(client, message: Message):
    is_search_locked = await get_config("search_locked")
    if is_search_locked and message.from_user.id != OWNER_ID:
        return await message.reply_text("**عـذراً، الـقـسـم مـغـلـق.**")

    if len(message.command) < 3: 
        return await message.reply_text("**يـرجـى كـتـابـة الـرابـط.**")
    
    query = message.text.split(None, 2)[2]
    mystic = await message.reply_text("**جـارٍ الـتـحـمـيـل...**")
    
    # دعم البلاي ليست
    if "list=" in query:
         return await Processor.download_playlist(client, mystic, query, True, message.from_user.first_name)
    
    try:
        title, _, duration_sec, _, vidid = await YouTube.details(query)
        if duration_sec is None: duration_sec = 0
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        
        is_owner = (message.from_user.id == OWNER_ID)
        quality_arg = "high" if is_owner else "mid"

        file_path = await Processor.download_file(yturl, quality_arg, True, title, vidid=vidid, is_owner=is_owner)
        
        await mystic.edit_text("**جـارٍ الـرفـع...**")
        await Processor.upload_alexa_style(client, mystic, file_path, True, title, duration_sec, message.from_user.first_name, vidid=vidid)
    except Exception as e:
        await mystic.edit_text(f"**حـدث خـطـأ:** {e}")


# --- الـكـول بـاك ---
@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
async def song_download_callback(client, CallbackQuery):
    is_search_locked = await get_config("search_locked")
    if is_search_locked and CallbackQuery.from_user.id != OWNER_ID:
        return await CallbackQuery.answer("قـسـم الـتـحـمـيـل مـغـلـق.", show_alert=True)

    is_inline_locked = await get_config("inline_locked")
    if is_inline_locked and CallbackQuery.from_user.id != OWNER_ID:
         return await CallbackQuery.answer("مـغـلـق.", show_alert=True)

    stype, quality_arg, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جـارٍ الـبـدء...")
    
    try: mystic = await CallbackQuery.message.edit_text("**جـارٍ الـتـحـمـيـل...**")
    except: mystic = await client.send_message(CallbackQuery.message.chat.id, "**جـارٍ الـتـحـمـيـل...**")
    
    is_video = (stype == "video")
    is_owner = (CallbackQuery.from_user.id == OWNER_ID)
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    
    try:
        title, _, duration_sec, _, _ = await YouTube.details(vidid)
        if duration_sec is None: duration_sec = 0

        file_path = await Processor.download_file(yturl, quality_arg, is_video, title, vidid=vidid, is_owner=is_owner)
        
        await mystic.edit_text("**جـارٍ الـرفـع...**")
        await Processor.upload_alexa_style(client, mystic, file_path, is_video, title, duration_sec, CallbackQuery.from_user.first_name, vidid=vidid)

    except Exception:
        await mystic.edit_text("**فـشـل الـتـحـمـيـل.**")

@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS)
async def song_helper_callback(client, CallbackQuery):
    is_search_locked = await get_config("search_locked")
    if is_search_locked and CallbackQuery.from_user.id != OWNER_ID:
        return await CallbackQuery.answer("مـغـلـق.", show_alert=True)

    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جـارٍ الـجـلـب...")
    buttons = await Processor.get_quality_buttons(vidid, stype)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS)
async def song_back_callback(client, CallbackQuery):
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    buttons = song_markup(None, vidid)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
