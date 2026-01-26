# تم التطوير بواسطة Certified Coders 2026
# الربط الوظيفي: العقل (YouTube) + المعالج المطور (Processor)
# ميزة الانتظار الذكي + الرفع التلقائي + أمر يوت

import asyncio
import os
from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup, 
    Message, 
    InputMediaAudio, 
    InputMediaVideo
)

from config import BANNED_USERS, SONG_DOWNLOAD_DURATION, SONG_DOWNLOAD_DURATION_LIMIT
from AnnieXMedia import app
# استيراد محرك البيانات للمعلومات الأساسية
from AnnieXMedia.platforms.Youtube import YouTube 
# استيراد المعالج المطور للتحميل والجودات والرفع
from AnnieXMedia.platforms.YTProcessor import Processor 
from AnnieXMedia.utils.inline.song import song_markup

COMMANDS = ["اغنية", "اغنيه", "هات", "ابعتلي"]

# --- معالجة البحث وطلب الاسم ---
@app.on_message(filters.command(COMMANDS, prefixes=["", "/"]) & ~BANNED_USERS)
async def song_processor(client, message: Message):
    """البحث عن المقطع مع تفعيل ميزة الانتظار الذكي من صاحب الأمر"""
    
    if len(message.command) < 2:
        try:
            # إرسال طلب الاسم والانتظار لمدة 10 ثوان من صاحب الأيدي
            prompt = await message.reply_text("ارسـل الان اسـم الـمـقـطـع")
            
            # الانتظار لرد من نفس المستخدم في نفس الدردشة
            response = await client.listen.Message(
                chat_id=message.chat.id,
                filters=filters.user(message.from_user.id),
                timeout=10
            )
            query = response.text
            await prompt.delete()
        except asyncio.TimeoutError:
            # رسالة الإغلاق في حال عدم الرد خلال 10 ثوان
            return await message.reply_text("تـم انـهـاء الـطـلـب لـعـدم وجـود طـلـب .")
        except Exception:
            return await message.reply_text("تـم انـهـاء الـطـلـب لـعـدم وجـود طـلـب .")
    else:
        query = message.text.split(None, 1)[1]
    
    mystic = await message.reply_text("جـاري الـبـحـث...")
    
    try:
        # جلب البيانات عبر المحرك الخفيف لضمان استقرار المكالمة
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(query)
        
        if int(duration_sec) > SONG_DOWNLOAD_DURATION_LIMIT:
            return await mystic.edit_text(f"الـمـقـطـع يـتـجـاوز الـحـد الـمـسـمـوح {SONG_DOWNLOAD_DURATION} دقـيـقـة")
        
        buttons = song_markup(None, vidid)
        await mystic.delete()
        await message.reply_photo(
            photo=thumbnail, 
            caption=f"الـعـنـوان: {title}\nالـمـدة: {duration_min}\n\nاخـتـر الـجـودة والـنـوع الـمـطـلوب:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        await mystic.edit_text("لـم يـتـم الـعـثـور عـلـى نـتـائج")

# --- أمر يوت للتحميل المباشر ---
@app.on_message(filters.command(["يوت"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_direct_processor(client, message: Message):
    """تحميل مباشر للصوت بجودة عالية عبر المعالج المطور"""
    if len(message.command) < 2:
        return await message.reply_text("يـرجى كـتـابـة اسـم الـمـقـطـع أو الـرابـط بـعـد الأمـر")
    
    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("جـاري الـتـحـمـيـل...")
    
    try:
        title, _, duration_sec, _, vidid = await YouTube.details(query)
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        
        # التحميل المباشر عبر المحرك المطور (Processor)
        file_path = await Processor.download_file(yturl, "bestaudio", False, title)
        
        await mystic.edit_text("جـاري الـرفـع...")
        
        # الرفع الذكي الذي يظهر الاسم والعنوان بشكل صحيح
        await Processor.send_smart_file(
            client, message.chat.id, file_path, False, 
            title, duration_sec, None, message.from_user.first_name
        )
        await mystic.delete()
    except Exception as e:
        await mystic.edit_text(f"حـدث خـطـأ أثـناء الـمعالجة: {e}")

# --- معالجة طلبات الجودة والتحميل ---
@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
async def song_download_callback(client, CallbackQuery):
    """التحميل عبر استبدال الوسائط لضمان السرعة"""
    stype, format_id, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جـاري تـحـضـيـر الـمـلـف...")
    
    mystic = await CallbackQuery.edit_message_text("جـاري الـتـحـمـيـل...")
    is_video = (stype == "video")
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    
    try:
        title, _, duration_sec, _, _ = await YouTube.details(vidid)
        # تنفيذ التحميل باستخدام المحرك المطور لتجاوز حظر يوتيوب
        file_path = await Processor.download_file(yturl, format_id, is_video, title)

        # تجهيز الصورة والبيانات للإرسال
        thumb = await CallbackQuery.message.download() if CallbackQuery.message.photo else None
        await mystic.edit_text("جـاري الـرفـع...")
        
        if is_video:
            media = InputMediaVideo(
                media=file_path, thumb=thumb,
                caption=f"الـعـنـوان: {title}\nطـلـب: {CallbackQuery.from_user.first_name}",
                duration=duration_sec, supports_streaming=True
            )
        else:
            media = InputMediaAudio(
                media=file_path, thumb=thumb,
                caption=f"الـعـنـوان: {title}\nطـلـب: {CallbackQuery.from_user.first_name}",
                duration=duration_sec, title=title, performer=CallbackQuery.from_user.first_name
            )

        try:
            # استبدال الرسالة الحالية بالملف المحمل
            await CallbackQuery.edit_message_media(media=media)
            if os.path.exists(file_path): os.remove(file_path)
        except Exception:
            # الرفع الاحتياطي للملفات الضخمة عبر المساعد
            await Processor.send_smart_file(
                client, CallbackQuery.message.chat.id, file_path, 
                is_video, title, duration_sec, thumb, CallbackQuery.from_user.first_name
            )
        
        await mystic.delete()
    except Exception as e:
        await mystic.edit_text(f"فـشـل الإرسـال: {e}")

# --- جلب الجودات المتاحة ---
@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS)
async def song_helper_callback(client, CallbackQuery):
    """جلب الجودات باستخدام المحرك المطور الذي يدعم الريموت"""
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جـاري جـلـب الـجـودات...")
    # استدعاء دالة الجودات من Processor لضمان عدم اختفائها
    buttons = await Processor.get_quality_buttons(vidid, stype)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS)
async def song_back_callback(client, CallbackQuery):
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    buttons = song_markup(None, vidid)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
