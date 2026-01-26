# Authored By Certified Coders © 2026
# الربط بين محرك البيانات ومعالج التحميل
# ميزة الانتظار الذكي: طلب اسم المقطع وانتظار المستخدم

import os
import asyncio
import yt_dlp
from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup, 
    Message, 
    InputMediaAudio, 
    InputMediaVideo
)

from config import BANNED_USERS, SONG_DOWNLOAD_DURATION, SONG_DOWNLOAD_DURATION_LIMIT
from AnnieXMedia import app
# استيراد محرك البيانات للمعلومات الأساسية والمكالمات
from AnnieXMedia.platforms.Youtube import YouTube 
# استيراد المعالج الجديد للتحميل والرفع المتقدم
from AnnieXMedia.platforms.YTProcessor import Processor 
from AnnieXMedia.utils.inline.song import song_markup

COMMANDS = ["اغنية", "اغنيه", "هات", "ابعتلي"]

# --- قسم البحث والمعالجة الذكية ---
@app.on_message(filters.command(COMMANDS, prefixes=["", "/"]) & ~BANNED_USERS)
async def song_processor(client, message: Message):
    """البحث عن المقطع مع ميزة انتظار الرد من نفس المستخدم"""
    
    # التحقق إذا كان الأمر مرسلاً بدون اسم المقطع
    if len(message.command) < 2:
        try:
            # طلب اسم المقطع وانتظار الرد من صاحب الأيدي حصراً لمدة 10 ثوانٍ
            prompt = await message.reply_text("ارسـل الان اسـم الـمـقـطـع")
            user_response = await client.listen.Message(
                chat_id=message.chat.id, 
                filters=filters.user(message.from_user.id), 
                timeout=10
            )
            query = user_response.text
            await prompt.delete()
        except asyncio.TimeoutError:
            # رسالة إنهاء الطلب في حال تجاوز الـ 10 ثوانٍ
            return await message.reply_text("تـم انـهـاء الـطـلـب لـعـدم وجـود طـلـب .")
    else:
        query = message.text.split(None, 1)[1]
    
    mystic = await message.reply_text("جـاري الـبـحـث...")
    
    try:
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(query)
        
        if int(duration_sec) > SONG_DOWNLOAD_DURATION_LIMIT:
            return await mystic.edit_text(f"الـمـقـطـع يـتـجـاوز الـحـد الـمـسـمـوح {SONG_DOWNLOAD_DURATION} دقـيـقـة")
        
        buttons = song_markup(None, vidid)
        await mystic.delete()
        await message.reply_photo(
            photo=thumbnail, 
            caption=f"**الـعـنـوان:** {title}\n**الـمـدة:** {duration_min}\n\nاخـتـر الـجـودة والـنـوع:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        await mystic.edit_text("لـم يـتـم الـعـثـور عـلـى نـتـائج")

# --- أمر يوت للتحميل المباشر ---
@app.on_message(filters.command(["يوت"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_direct_processor(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("يـرجى كـتـابـة اسـم الـمـقـطـع أو الـرابـط")
    
    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("جـاري الـتـحـمـيـل...")
    
    try:
        title, _, duration_sec, _, vidid = await YouTube.details(query)
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        
        file_path = await Processor.download_file(yturl, "bestaudio", False, title)
        
        await mystic.edit_text("جـاري الـرفـع...")
        
        await Processor.send_nuclear_file(
            client, message.chat.id, file_path, False, 
            title, duration_sec, None, message.from_user.first_name
        )
        await mystic.delete()
    except Exception as e:
        await mystic.edit_text(f"حـدث خـطـأ: {e}")

# --- معالجة الأزرار واستبدال الميديا ---
@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
async def song_download_callback(client, CallbackQuery):
    stype, format_id, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جـاري الـتـنـفـيذ...")
    
    mystic = await CallbackQuery.edit_message_text("جـاري الـتـحـمـيـل...")
    is_video = (stype == "video")
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    
    try:
        title, _, duration_sec, _, _ = await YouTube.details(vidid)
        # استخدام المعالج الجديد لتخطي حظر يوتيوب وجلب الجودات
        file_path = await Processor.download_file(yturl, format_id, is_video, title)

        thumb = await CallbackQuery.message.download() if CallbackQuery.message.photo else None
        await mystic.edit_text("جـاري الـرفـع...")
        
        if is_video:
            media = InputMediaVideo(
                media=file_path, thumb=thumb,
                caption=f"**الـفـيـدـيو:** {title}\n**طـلـب:** {CallbackQuery.from_user.first_name}",
                duration=duration_sec, supports_streaming=True
            )
        else:
            media = InputMediaAudio(
                media=file_path, thumb=thumb,
                caption=f"**الـصـوت:** {title}\n**طـلـب:** {CallbackQuery.from_user.first_name}",
                duration=duration_sec, title=title, performer="System"
            )

        try:
            await CallbackQuery.edit_message_media(media=media)
            if os.path.exists(file_path): os.remove(file_path)
        except Exception:
            # حل بديل للملفات الكبيرة التي تتطلب الحساب المساعد
            await Processor.send_nuclear_file(
                client, CallbackQuery.message.chat.id, file_path, 
                is_video, title, duration_sec, thumb, CallbackQuery.from_user.first_name
            )
        
        await mystic.delete()
    except Exception as e:
        await mystic.edit_text(f"فـشـل الإرسـال: {e}")

# --- جلب الجودات المتاحة عبر الريموت ---
@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS)
async def song_helper_callback(client, CallbackQuery):
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جـاري جـلـب الـجـودات الـمـتـاحـة...")
    # استدعاء المعالج المتقدم لفك التشفير وضمان ظهور الجودات
    buttons = await Processor.get_quality_buttons(vidid, stype)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS)
async def song_back_callback(client, CallbackQuery):
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    buttons = song_markup(None, vidid)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
