# Authored By Certified Coders © 2025
# Alexa Technique Integration: Instant Media Replacement & RAM Caching
import os
import yt_dlp
from pyrogram import filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup, 
    Message, 
    InputMediaAudio, 
    InputMediaVideo
)

from config import BANNED_USERS, SONG_DOWNLOAD_DURATION, SONG_DOWNLOAD_DURATION_LIMIT
from AnnieXMedia import YouTube, app
from AnnieXMedia.utils.inline.song import song_markup

COMMANDS = ["اغنية", "هات", "ابعتلي"]

@app.on_message(filters.command(COMMANDS, prefixes=["", "/"]) & ~BANNED_USERS)
async def song_processor(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("يـرجى كـتـابـة اسـم الـمـقـطـع بـعـد الأمـر")
    
    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("جـاري الـبـحـث...")
    
    try:
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(query)
        if int(duration_sec) > SONG_DOWNLOAD_DURATION_LIMIT:
            return await mystic.edit_text(f"الـمـقـطـع يـتـجاوز الـحد الـمـسـمـوح {SONG_DOWNLOAD_DURATION} دقـيـقـة")
        
        buttons = song_markup(None, vidid)
        await mystic.delete()
        await message.reply_photo(
            photo=thumbnail, 
            caption=f"**الـعـنـوان:** {title}\n**الـمـدة:** {duration_min}\n\nاخـتـر الـجـودة والـنـوع:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        await mystic.edit_text("لـم يـتـم الـعـثـور عـلى نـتـائج")

@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
async def song_download_callback(client, CallbackQuery):
    """تطبيق تكنيك أليكسا: الإرسال في ثانية واحدة عبر استبدال الميديا"""
    stype, format_id, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    
    # 1. إجابة الكولباك فوراً لإيقاف علامة التحميل عند المستخدم
    await CallbackQuery.answer("جـاري الـتـحـضـيـر النووي...")
    
    mystic = await CallbackQuery.edit_message_text("جـاري الـتـنـزيـل...")
    is_video = (stype == "video")
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    
    try:
        # 2. التحميل (المحرك بيفحص الرام ديسك أولاً، لو موجود بيرجع المسار فوراً)
        file_path, direct = await YouTube.download(
            yturl, mystic, 
            songvideo=is_video, 
            songaudio=not is_video, 
            format_id=format_id
        )

        # 3. جلب بيانات المقطع
        with yt_dlp.YoutubeDL({"quiet": True}) as ytdl:
            info = ytdl.extract_info(yturl, download=False)
        
        title = info.get("title", "Unknown")
        duration = info.get("duration", 0)
        thumb = await CallbackQuery.message.download() if CallbackQuery.message.photo else None

        # 🚀 سر أليكسا: استبدال الصورة بالملف مباشرة (Edit Media) 🚀
        await mystic.edit_text("جـاري الإرسـال الـفـوري...")
        
        if is_video:
            media = InputMediaVideo(
                media=file_path,
                thumb=thumb,
                caption=f"**الـفـيـديـو:** {title}\n**طـلـب:** {CallbackQuery.from_user.first_name}",
                duration=duration,
                supports_streaming=True
            )
        else:
            media = InputMediaAudio(
                media=file_path,
                thumb=thumb,
                caption=f"**الـصـوت:** {title}\n**طـلـب:** {CallbackQuery.from_user.first_name}",
                duration=duration,
                title=title,
                performer="المحرك النووي"
            )

        # الإرسال الذكي: استبدال الرسالة الحالية بالملف
        try:
            await CallbackQuery.edit_message_media(media=media)
            # تنظيف الرام ديسك بعد الإرسال
            if os.path.exists(file_path): os.remove(file_path)
            if thumb and os.path.exists(thumb): os.remove(thumb)
        except Exception:
            # لو فشل الاستبدال (مثلاً ملف أكبر من 50MB)، نستخدم دالة الرفع النووي
            await YouTube.send_nuclear_file(
                client, CallbackQuery.message.chat.id, file_path, direct, 
                is_video, title, duration, thumb, CallbackQuery.from_user.first_name
            )
        
        await mystic.delete()

    except Exception as e:
        await mystic.edit_text(f"فـشل الإرسـال: {e}")

# بقية الأوامر (song_helper و song_back) تظل كما هي لضمان استقرار التنقل
@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS)
async def song_helper_callback(client, CallbackQuery):
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جـاري جـلـب الـجـودات...")
    buttons = await YouTube.get_quality_buttons(vidid, stype)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS)
async def song_back_callback(client, CallbackQuery):
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    buttons = song_markup(None, vidid)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
