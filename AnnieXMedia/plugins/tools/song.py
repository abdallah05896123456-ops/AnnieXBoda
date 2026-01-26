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

# استيراد الأدوات من سورسك AnnieXMedia
from config import BANNED_USERS, SONG_DOWNLOAD_DURATION, SONG_DOWNLOAD_DURATION_LIMIT
from AnnieXMedia import YouTube, app
from AnnieXMedia.utils.formatters import convert_bytes
from AnnieXMedia.utils.inline.song import song_markup

# الأوامر المطلوبة: اغنية، هات، ابعتلي (تعمل بـ / وبدونه)
COMMANDS = ["اغنية", "هات", "ابعتلي"]

@app.on_message(filters.command(COMMANDS, prefixes=["", "/"]) & filters.private & ~BANNED_USERS)
async def song_private_processor(client, message: Message):
    """المرحلة الأولى: البحث عن المقطع وعرض خيارات التحميل"""
    if len(message.command) < 2:
        return await message.reply_text("يـرجى كـتـابـة اسـم الـمـقـطـع بـعـد الأمـر")

    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("جـاري الـبـحـث فـي قـواعـد الـبـيـانـات")

    try:
        # استخدام المحرك النووي لجلب التفاصيل
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(query)
    except Exception:
        return await mystic.edit_text("تـعـذر الـعـثـور عـلى نـتـائج لـهذا الـبـحـث")

    # التحقق من طول المقطع بناءً على إعدادات الـ Config
    if int(duration_sec) > SONG_DOWNLOAD_DURATION_LIMIT:
        return await mystic.edit_text(f"الـمـقـطـع طـويـل جـداً. الـحـد الأقـصى الـمـسـمـوح بـه هـو {SONG_DOWNLOAD_DURATION} دقـيـقـة")

    # استدعاء ملف الأزرار الذي أنشأته في المسار الخاص به
    buttons = song_markup(None, vidid)
    await mystic.delete()
    
    return await message.reply_photo(
        photo=thumbnail,
        caption=f"الـعـنـوان: {title}\nالـمـدة: {duration_min}\n\nاخـتـر نـوع الـتـحـمـيـل الـمـطـلـوب:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS)
async def song_helper_callback(client, CallbackQuery):
    """المرحلة الثانية: جلب الجودات المتاحة للمقطع المختار"""
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    stype, vidid = callback_request.split("|")
    
    await CallbackQuery.answer("جـاري جـلـب الـجـودات")
    
    try:
        # جلب قائمة الجودات من المحرك النووي
        formats_available, link = await YouTube.formats(vidid, True)
    except Exception:
        return await CallbackQuery.edit_message_text("حـدث خـطأ أثـناء جـلـب قـائـمة الـجـودات")

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
                fom = x.get("format_id")
                keyboard.append([InlineKeyboardButton(text=f"صـوت {form} - الـحـجم {sz}", callback_data=f"song_download {stype}|{fom}|{vidid}")])
    else:
        # حصر الجودات لضمان التوافق التام (AVC)
        allowed_ids = [160, 133, 134, 135, 136, 137, 298, 299, 264, 304, 266]
        for x in formats_available:
            if x.get("filesize") is None: continue
            if int(x.get("format_id")) not in allowed_ids: continue
            sz = convert_bytes(x.get("filesize"))
            res = x.get("format").split("-")[1] if "-" in x.get("format") else "Video"
            keyboard.append([InlineKeyboardButton(text=f"فـيـديـو {res} - الـحـجم {sz}", callback_data=f"song_download {stype}|{x['format_id']}|{vidid}")])

    keyboard.append([InlineKeyboardButton(text="رجـوع", callback_data=f"song_back {stype}|{vidid}"), 
                     InlineKeyboardButton(text="إغـلاق", callback_data="close")])
    
    return await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
async def song_download_final(client, CallbackQuery):
    """المرحلة الثالثة: التحميل عبر Aria2c في الرام ديسك والرفع الفوري"""
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    stype, format_id, vidid = callback_request.split("|")
    
    mystic = await CallbackQuery.edit_message_text("جـاري الـتـحـمـيـل إلـى الـرام")
    
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    
    try:
        # المحرك النووي يرجع المسار في /dev/shm وحالة الرابط المباشر
        file_path, direct = await YouTube.download(
            yturl,
            mystic,
            songvideo=(stype == "video"),
            songaudio=(stype == "audio"),
            format_id=format_id,
            title=f"Annie_{vidid}"
        )
    except Exception as e:
        return await mystic.edit_text(f"فـشل الـنـظام في تـنـفيذ الـتـحـميل: {e}")

    await mystic.edit_text("جـاري الـرفـع الـفـوري")
    
    # جلب تفاصيل المقطع النهائية للرفع
    with yt_dlp.YoutubeDL({"quiet": True}) as ytdl:
        info = ytdl.extract_info(yturl, download=False)
    
    title = info.get("title", "Unknown")
    thumbnail = await CallbackQuery.message.download() if CallbackQuery.message.photo else None

    try:
        if stype == "video":
            await app.send_chat_action(CallbackQuery.message.chat.id, enums.ChatAction.UPLOAD_VIDEO)
            await CallbackQuery.message.reply_video(
                video=file_path,
                duration=info.get("duration", 0),
                caption=title,
                thumb=thumbnail,
                supports_streaming=True
            )
        else:
            await app.send_chat_action(CallbackQuery.message.chat.id, enums.ChatAction.UPLOAD_AUDIO)
            await CallbackQuery.message.reply_audio(
                audio=file_path,
                caption=title,
                duration=info.get("duration", 0),
                performer=info.get("uploader", "AnnieXMedia"),
                thumb=thumbnail,
                title=title
            )
        await mystic.delete()
    except Exception:
        await mystic.edit_text("حـدث خـطأ أثـناء الـرفع إلـى تـلـيـجرام")

    # تنظيف الـ RAM Disk والملفات المؤقتة
    if not direct and os.path.exists(file_path):
        os.remove(file_path)
    if thumbnail and os.path.exists(thumbnail):
        os.remove(thumbnail)

@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS)
async def song_back_callback(client, CallbackQuery):
    """الرجوع للقائمة الرئيسية"""
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    stype, vidid = callback_request.split("|")
    buttons = song_markup(None, vidid)
    return await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.command(COMMANDS, prefixes=["", "/"]) & filters.group & ~BANNED_USERS)
async def song_group_filter(client, message: Message):
    """منع استخدام الأوامر في المجموعات للحفاظ على الهدوء"""
    upl = InlineKeyboardMarkup([[InlineKeyboardButton(text="اضـغـط لـلـطـلب"، url=f"https://t.me/{app.username}?start=song")]])
    await message.reply_text("طـلب الأغـاني مـتـاح فـي الـخـاص فـقـط", reply_markup=upl)
