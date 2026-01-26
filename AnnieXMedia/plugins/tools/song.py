import os
import re
import yt_dlp
from pyrogram import enums, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaAudio,
    InputMediaVideo,
    Message,
)

from config import BANNED_USERS, SONG_DOWNLOAD_DURATION, SONG_DOWNLOAD_DURATION_LIMIT
from AnnieXMedia import YouTube, app
from AnnieXMedia.utils.formatters import convert_bytes
from AnnieXMedia.utils.inline.song import song_markup

COMMANDS = ["اغنية", "هات", "ابعتلي"]

@app.on_message(filters.command(COMMANDS, prefixes=["", "/"]) & ~BANNED_USERS)
async def song_processor(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("يرجى كتابة اسم المقطع")

    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("جاري البحث")

    try:
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(query)
    except Exception:
        return await mystic.edit_text("لم يتم العثور على نتائج")

    if int(duration_sec) > SONG_DOWNLOAD_DURATION_LIMIT:
        return await mystic.edit_text(f"المقطع يتجاوز الحد المسموح {SONG_DOWNLOAD_DURATION} دقيقة")

    buttons = song_markup(None, vidid)
    await mystic.delete()
    
    return await message.reply_photo(
        photo=thumbnail,
        caption=f"العنوان: {title}\nالمدة: {duration_min}\n\nاختر نوع الملف المطلوب:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

@app.on_message(filters.command(["يوت"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_processor(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("يرجى كتابة الاسم بعد الأمر")

    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("جاري التنزيل")

    try:
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(query)
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        
        file_path, direct = await YouTube.download(
            yturl, mystic, songaudio=True, title=f"Yut_{vidid}"
        )

        if not file_path:
            return await mystic.edit_text("حدث خطأ في جلب الملف")

        await mystic.edit_text("جاري الرفع")

        await message.reply_audio(
            audio=file_path,
            duration=duration_sec,
            title=title,
            caption=f"طـلـب بـواسـطـة {message.from_user.first_name}"
        )
        await mystic.delete()
        if not direct and os.path.exists(file_path): os.remove(file_path)

    except Exception:
        await mystic.edit_text("حدث خطأ في النظام")

@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS)
async def song_helper_cb(client, CallbackQuery):
    callback_data = CallbackQuery.data.strip()
    stype, vidid = callback_data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جاري التحضير")
    
    try:
        formats_available, _ = await YouTube.formats(vidid, True)
    except Exception:
        return await CallbackQuery.edit_message_text("تعذر جلب البيانات")

    keyboard = []
    if stype == "audio":
        done = []
        for x in formats_available:
            check = x.get("format")
            if "audio" in check:
                if x.get("filesize") is None: continue
                form = x.get("format_note", "Audio").title()
                if form not in done: done.append(form)
                else: continue
                sz = convert_bytes(x.get("filesize"))
                keyboard.append([InlineKeyboardButton(text=f"صوت {form} الحجم {sz}", callback_data=f"song_download {stype}|{x.get('format_id')}|{vidid}")])
    else:
        allowed_ids = [160, 133, 134, 135, 136, 137, 298, 299, 264, 304, 266]
        for x in formats_available:
            if x.get("filesize") is None or int(x.get("format_id")) not in allowed_ids: continue
            sz = convert_bytes(x.get("filesize"))
            res = x.get("format").split("-")[1] if "-" in x.get("format") else "Video"
            keyboard.append([InlineKeyboardButton(text=f"فيديو {res} الحجم {sz}", callback_data=f"song_download {stype}|{x.get('format_id')}|{vidid}")])

    keyboard.append([InlineKeyboardButton(text="رجوع", callback_data=f"song_back {stype}|{vidid}")])
    keyboard.append([InlineKeyboardButton(text="إغلاق", callback_data="close")])
    return await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
async def song_download_cb(client, CallbackQuery):
    callback_data = CallbackQuery.data.strip()
    stype, format_id, vidid = callback_data.split(None, 1)[1].split("|")
    mystic = await CallbackQuery.edit_message_text("جاري التنزيل")
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    
    try:
        file_path, direct = await YouTube.download(
            yturl, mystic, songvideo=(stype == "video"), songaudio=(stype == "audio"), format_id=format_id, title=f"Annie_{vidid}"
        )
        await mystic.edit_text("جاري الرفع")
        
        with yt_dlp.YoutubeDL({"quiet": True}) as ytdl:
            info = ytdl.extract_info(yturl, download=False)
        
        thumb = await CallbackQuery.message.download() if CallbackQuery.message.photo else None
        caption_text = f"طـلـب بـواسـطـة {CallbackQuery.from_user.first_name}"

        if stype == "video":
            await CallbackQuery.message.reply_video(video=file_path, duration=info.get("duration", 0), caption=caption_text, thumb=thumb, supports_streaming=True)
        else:
            await CallbackQuery.message.reply_audio(audio=file_path, caption=caption_text, duration=info.get("duration", 0), thumb=thumb, title=info.get("title"))
        
        await mystic.delete()
        if not direct and os.path.exists(file_path): os.remove(file_path)
        if thumb and os.path.exists(thumb): os.remove(thumb)
    except Exception:
        await mystic.edit_text("فشل إرسال الملف")

@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS)
async def song_back_cb(client, CallbackQuery):
    callback_data = CallbackQuery.data.strip()
    stype, vidid = callback_data.split(None, 1)[1].split("|")
    buttons = song_markup(None, vidid)
    return await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
