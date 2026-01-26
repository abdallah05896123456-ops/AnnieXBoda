# Authored By Certified Coders © 2026
# النظام المتقدم: الربط بين محرك البيانات ومعالج التحميل
# المميزات: استبدال الوسائط الفوري، التخزين المؤقت في الرام، وتجاوز قيود التحقق

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
from AnnieXMedia import app
# استيراد محرك البيانات للمكالمات والمعلومات الأساسية
from AnnieXMedia.platforms.Youtube import YouTube 
# استيراد معالج التحميل للعمليات الثقيلة والرفع المتقدم
from AnnieXMedia.platforms.YTProcessor import Processor 
from AnnieXMedia.utils.inline.song import song_markup

COMMANDS = ["اغنية", "هات", "ابعتلي"]

# --- أمر البحث والاستعلام ---
@app.on_message(filters.command(COMMANDS, prefixes=["", "/"]) & ~BANNED_USERS)
async def song_processor(client, message: Message):
    """البحث الأولي وجلب البيانات من محرك البحث الخفيف"""
    if len(message.command) < 2:
        return await message.reply_text("⚠️ يـرجى كـتـابـة اسـم الـمـقـطـع بـعـد الأمـر")
    
    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("🔍 جـاري الـبـحـث في قـاعدة الـبيـانـات...")
    
    try:
        # استخدام المحرك الخفيف لضمان سرعة الاستجابة وعدم الضغط على موارد المكالمة
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(query)
        
        if int(duration_sec) > SONG_DOWNLOAD_DURATION_LIMIT:
            return await mystic.edit_text(f"❌ الـمـقـطـع يـتـجاوز الـحد الـمـسـمـوح {SONG_DOWNLOAD_DURATION} دقـيـقة")
        
        buttons = song_markup(None, vidid)
        await mystic.delete()
        await message.reply_photo(
            photo=thumbnail, 
            caption=f"📌 **الـعـنـوان:** {title}\n⏱ **الـمـدة:** {duration_min}\n\n🎬 اخـتـر الـجـودة والـنـوع الـمطلوب:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        await mystic.edit_text("❌ لـم يـتـم الـعـثـور عـلى نـتـائج طـبـقاً لـبـحـثك.")

# --- أمر التحميل المباشر (يوت) ---
@app.on_message(filters.command(["يوت"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_direct_processor(client, message: Message):
    """أمر يوت: التحميل المباشر والرفع المتقدم عبر معالج التحميل"""
    if len(message.command) < 2:
        return await message.reply_text("⚠️ يـرجى كـتـابـة اسـم الـمـقـطـع أو الرابط بـعـد الأمـر")
    
    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("🚀 جـاري الـتـنـزيـل الـمـبـاشـر بـأقـصى سـرعـة...")
    
    try:
        # جلب البيانات الأساسية للرابط
        title, _, duration_sec, thumb_url, vidid = await YouTube.details(query)
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        
        # استدعاء معالج التحميل المتقدم (Processor)
        file_path = await Processor.download_file(yturl, "bestaudio", False, title)
        
        await mystic.edit_text("📤 جـاري الـرفـع الـمـتـقـدم إلـى الـدردشـة...")
        
        # استخدام تكنيك الرفع الذكي (المساعد في الخلفية)
        await Processor.send_nuclear_file(
            client, message.chat.id, file_path, False, 
            title, duration_sec, None, message.from_user.first_name
        )
        await mystic.delete()
    except Exception as e:
        await mystic.edit_text(f"⚠️ حـدث خـطأ في نـظام الـتحـمـيل: {e}")

# --- معالجة طلبات التحميل من الأزرار ---
@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
async def song_download_callback(client, CallbackQuery):
    """تطبيق تكنيك استبدال الوسائط الفوري"""
    stype, format_id, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("✅ جـاري مـعـالـجـة طـلـبك...")
    
    mystic = await CallbackQuery.edit_message_text("⏳ جـاري تـحـضـيـر الـمـلـف، يـرجى الانـتـظـار...")
    is_video = (stype == "video")
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    
    try:
        # جلب تفاصيل المقطع لبدء المعالجة
        title, _, duration_sec, _, _ = await YouTube.details(vidid)
        
        # التحميل عبر المعالج المخصص لفك التشفير وتجاوز الحظر
        file_path = await Processor.download_file(yturl, format_id, is_video, title)

        # تجهيز الصورة المصغرة
        thumb = await CallbackQuery.message.download() if CallbackQuery.message.photo else None
        await mystic.edit_text("🔄 جـاري الإرسـال الـفـوري...")
        
        if is_video:
            media = InputMediaVideo(
                media=file_path, thumb=thumb,
                caption=f"🎥 **الـفـيـديـو:** {title}\n👤 **طـلـب:** {CallbackQuery.from_user.first_name}",
                duration=duration_sec, supports_streaming=True
            )
        else:
            media = InputMediaAudio(
                media=file_path, thumb=thumb,
                caption=f"🎵 **الـصـوت:** {title}\n👤 **طـلـب:** {CallbackQuery.from_user.first_name}",
                duration=duration_sec, title=title, performer="System Processor"
            )

        try:
            # استبدال الرسالة الحالية بالملف لضمان السرعة
            await CallbackQuery.edit_message_media(media=media)
            if os.path.exists(file_path): os.remove(file_path)
        except Exception:
            # في حال تجاوز الحجم المسموح، يتم استخدام الرفع المساعد
            await Processor.send_nuclear_file(
                client, CallbackQuery.message.chat.id, file_path, 
                is_video, title, duration_sec, thumb, CallbackQuery.from_user.first_name
            )
        
        await mystic.delete()
    except Exception as e:
        await mystic.edit_text(f"❌ فـشل الإرسـال: {e}")

# --- معالجة الجودات والتنقل ---
@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS)
async def song_helper_callback(client, CallbackQuery):
    """جلب الجودات المتاحة عبر المعالج المتقدم لفك التشفير"""
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("🛠 جـاري فـك تـشـفـير الـجودات...")
    # استخدام المعالج لضمان ظهور الجودات حتى في المقاطع المشفرة
    buttons = await Processor.get_quality_buttons(vidid, stype)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS)
async def song_back_callback(client, CallbackQuery):
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    buttons = song_markup(None, vidid)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
