# Authored By Certified Coders © 2026
# System: Song Plugin | Direct Stream Pipe (No Download) | Instant Upload
# Optimized for AnnieXMedia Bot Folder Structure

import asyncio
import os
import re
import yt_dlp
from pyrogram import filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    Message, 
    InputMediaAudio, 
    InputMediaVideo
)
from motor.motor_asyncio import AsyncIOMotorClient

# Config & Imports
from config import (
    BANNED_USERS, 
    SONG_DOWNLOAD_DURATION, 
    SONG_DOWNLOAD_DURATION_LIMIT, 
    OWNER_ID, 
    MONGO_DB_URI
)
from AnnieXMedia import app
from AnnieXMedia.platforms.Youtube import YouTube 
from AnnieXMedia.platforms.YTProcessor import Processor 
from AnnieXMedia.utils.inline.song import song_markup

# ==========================================================
# Database & Config
# ==========================================================

SUDO_USERS = OWNER_ID if isinstance(OWNER_ID, list) else [OWNER_ID]
_mongo_client_ = AsyncIOMotorClient(MONGO_DB_URI)
mongodb = _mongo_client_.Annie
songdb = mongodb.song_settings

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

# ==========================================================
# Admin Commands (Updated)
# ==========================================================

@app.on_message(filters.command(["قفل التنزيل", "تعطيل التنزيل"], prefixes=["", "/"]) & filters.user(SUDO_USERS))
async def lock_search(client, message):
    await set_config("search_locked", True)
    await message.reply_text("**تم قفل التنزيل.**")

@app.on_message(filters.command(["فتح التنزيل", "تفعيل التنزيل"], prefixes=["", "/"]) & filters.user(SUDO_USERS))
async def unlock_search(client, message):
    await set_config("search_locked", False)
    await message.reply_text("**تم فتح التنزيل.**")

# ==========================================================
# Main Search Engine
# ==========================================================

@app.on_message(filters.regex(r"^/?(اغنية|اغنيه|هات|هاتلي|ابعتلي|song|video|تحميل|يوتيوب)(?:\s+(فيد|فيديو|video))?(?:\s+(.+))?$") & ~BANNED_USERS, group=5)
async def song_search_handler(client, message: Message):
    
    if await get_config("search_locked") and message.from_user.id not in SUDO_USERS:
        return await message.reply_text("**القسم مغلق حالياً.**")

    match = re.match(r"^/?(اغنية|اغنيه|هات|هاتلي|ابعتلي|song|video|تحميل|يوتيوب)(?:\s+(فيد|فيديو|video))?(?:\s+(.+))?$", message.text)
    if not match: return
    
    query = match.group(3)
    if not query:
        return await message.reply_text("**أرسل اسم الأغنية أو الرابط.**")

    mystic = await message.reply_text("**جـارٍ الـبـحـث...**")

    # Playlist Support (Processor handles it well)
    if "list=" in query:
        return await Processor.download_playlist(client, mystic, query, False, message.from_user.first_name)

    try:
        # 1. Fetch Details Fast
        (
            title,
            duration_min,
            duration_sec,
            thumbnail,
            vidid,
        ) = await YouTube.details(query)

        if str(duration_min) == "None":
            return await mystic.edit_text("**لم يتم العثور على نتائج.**")
            
        if int(duration_sec) > 14400: 
            return await mystic.edit_text("**عذراً، المقطع طويل جداً.**")
        
        # 2. Show Results with Buttons
        buttons = song_markup(None, vidid)
        
        await mystic.delete()
        
        # Sending photo allows us to download it locally later for muxing
        await message.reply_photo(
            thumbnail,
            caption=f"**الـعـنـوان:** {title}\n**الـمـدة:** {duration_min}\n\n**اخـتـر الـجـودة والـنـوع:**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        await mystic.edit_text("**حدث خطأ أثناء البحث.**")

# ==========================================================
# Direct Command (Yout) - PIPING MODE
# ==========================================================

@app.on_message(filters.command(["يوت", "yt"], prefixes=["", "/"]) & ~BANNED_USERS)
async def direct_stream_handler(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("**ضع الرابط بجانب الأمر.**")
    
    query = message.text.split(None, 1)[1]
    is_video = "فيد" in message.command[0] or "video" in message.command[0]
    
    mystic = await message.reply_text("**جـارٍ الـمـعـالـجـة...**")
    
    try:
        # 1. Get Details
        title, _, duration_sec, thumbnail, vidid = await YouTube.details(query)
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        
        # 2. Download Thumbnail Locally (Fast)
        # We need a local file for Pyrogram to attach it properly
        thumb_path = f"downloads/{vidid}.jpg"
        if not os.path.exists("downloads"): os.makedirs("downloads")
        # استخدام yt-dlp او wget لتحميل الصورة بسرعة
        await asyncio.create_subprocess_shell(f"wget -q -O {thumb_path} {thumbnail}")
        
        # 3. Get Direct Stream Link (No Download!)
        stream_link = await YouTube.get_direct_stream_link(yturl, is_video)
        
        if not stream_link:
            return await mystic.edit_text("**فشل استخراج الرابط المباشر.**")

        # 4. Instant Upload via URL (Piping)
        await mystic.edit_text("**جـارٍ الـرفـع...**")
        
        if is_video:
            await client.send_video(
                message.chat.id,
                video=stream_link, # Passing URL directly!
                caption=title,
                duration=int(duration_sec),
                thumb=thumb_path,
                supports_streaming=True
            )
        else:
            await client.send_audio(
                message.chat.id,
                audio=stream_link, # Passing URL directly!
                caption=title,
                title=title,
                performer="Annie Music",
                thumb=thumb_path
            )
            
        await mystic.delete()
        if os.path.exists(thumb_path): os.remove(thumb_path)

    except Exception as e:
        await mystic.edit_text(f"**خطأ:** {e}")

# ==========================================================
# Callbacks - (The Speed Secret ⚡)
# ==========================================================

@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
async def song_download_callback(client, CallbackQuery):
    data = CallbackQuery.data.split(None, 1)[1]
    stype, format_id, vidid = data.split("|")
    
    await CallbackQuery.answer("جـارٍ بـدء الـتـحـمـيـل...", cache_time=0)
    
    # Fast Edit
    mystic = await CallbackQuery.edit_message_text("**⬇️ جـارٍ الـتـحـمـيـل مـن الـسـيـرفـر...**")
    
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    is_video = (stype == "video")
    
    try:
        # 1. Quick Info Fetch
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            x = ydl.extract_info(yturl, download=False)
        
        title = (x["title"]).title()
        title = re.sub("\W+", " ", title)
        duration = x["duration"]
        
        # 2. Download Thumbnail from Telegram (Best for Speed/Format)
        thumb_path = await CallbackQuery.message.download(file_name=f"{vidid}.jpg")
        
        # 3. Get Direct Link (Zero Download Time)
        stream_link = await YouTube.get_direct_stream_link(yturl, is_video)
        
        # Fallback Logic
        if not stream_link:
             # If stream fails, download fully using Processor (Aria2c)
             file_path = await YouTube.download(
                yturl, mystic, songvideo=is_video, songaudio=not is_video, title=title
             )
             stream_link = file_path 

        # 4. Instant Edit Media (Zero Latency Upload)
        await mystic.edit_text("**⬆️ جـارٍ الـرفـع...**")
        
        if is_video:
            media = InputMediaVideo(
                media=stream_link,
                duration=duration,
                width=CallbackQuery.message.photo.width if CallbackQuery.message.photo else 0,
                height=CallbackQuery.message.photo.height if CallbackQuery.message.photo else 0,
                thumb=thumb_path,
                caption=title,
                supports_streaming=True,
            )
            await client.send_chat_action(CallbackQuery.message.chat.id, enums.ChatAction.UPLOAD_VIDEO)
        else:
            media = InputMediaAudio(
                media=stream_link,
                caption=title,
                thumb=thumb_path,
                title=title,
                performer=x.get("uploader", "Annie Music"),
            )
            await client.send_chat_action(CallbackQuery.message.chat.id, enums.ChatAction.UPLOAD_AUDIO)
            
        await CallbackQuery.edit_message_media(media=media)
        
    except Exception as e:
        await mystic.edit_text(f"**فشل التحميل:** {e}")
        
    finally:
        # Cleanup
        if thumb_path and os.path.exists(thumb_path): 
            os.remove(thumb_path)
        # If we downloaded a file (fallback), delete it
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)


@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS)
async def song_helper_callback(client, CallbackQuery):
    data = CallbackQuery.data.split(None, 1)[1]
    stype, vidid = data.split("|")
    await CallbackQuery.answer("جـارٍ جـلـب الـجـودات...", cache_time=0)
    
    # Using YouTube.formats for speed (Alexa style)
    try:
        formats_available, link = await YouTube.formats(vidid, True)
    except:
        return await CallbackQuery.edit_message_text("**حدث خطأ في جلب الجودات.**")
        
    keyboard = []
    done = []
    
    if stype == "audio":
        for x in formats_available:
            if "audio" in x["format"]:
                if x["filesize"] is None: continue
                form = "High" if "high" in x.get("format_note", "").lower() else "Mid"
                sz = f"{int(x['filesize'])/(1024*1024):.1f}MB"
                fom = x["format_id"]
                if form not in done:
                    keyboard.append([InlineKeyboardButton(text=f"{form} Quality ({sz})", callback_data=f"song_download {stype}|{fom}|{vidid}")])
                    done.append(form)
                    
    else: # Video
        allowed_res = ["144p", "240p", "360p", "480p", "720p"]
        for x in formats_available:
            check = x["format"]
            if x["filesize"] is None: continue
            res = None
            for r in allowed_res:
                if r in check: res = r; break
            
            if res and res not in done:
                sz = f"{int(x['filesize'])/(1024*1024):.1f}MB"
                keyboard.append([InlineKeyboardButton(text=f"{res} ({sz})", callback_data=f"song_download {stype}|{x['format_id']}|{vidid}")])
                done.append(res)

    keyboard.append([
        InlineKeyboardButton(text="رجوع", callback_data=f"song_back {stype}|{vidid}"),
        InlineKeyboardButton(text="إغلاق", callback_data="close")
    ])
    
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))


@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS)
async def song_back_callback(client, CallbackQuery):
    data = CallbackQuery.data.split(None, 1)[1]
    vidid = data.split("|")[1] if "|" in data else data
    buttons = song_markup(None, vidid)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
