import os
import yt_dlp
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message

# استيراد الأدوات والمحرك النووي المركزي
from config import BANNED_USERS, SONG_DOWNLOAD_DURATION, SONG_DOWNLOAD_DURATION_LIMIT
from AnnieXMedia import YouTube, app
from AnnieXMedia.utils.inline.song import song_markup

# الأوامر الرسمية المعتمدة
COMMANDS = ["اغنية", "هات", "ابعتلي"]

@app.on_message(filters.command(COMMANDS, prefixes=["", "/"]) & ~BANNED_USERS)
async def song_processor(client, message: Message):
    """البحث وعرض القائمة الرئيسية بنسق مطول"""
    if len(message.command) < 2:
        return await message.reply_text("يـرجى كـتـابـة اسـم الـمـقـطـع بـعـد الأمـر")
    
    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("جـاري الـبـحـث")
    
    try:
        # استدعاء تفاصيل المقطع من المحرك المركزي
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(query)
        
        if int(duration_sec) > SONG_DOWNLOAD_DURATION_LIMIT:
            return await mystic.edit_text(f"الـمـقـطـع يـتـجاوز الـحد الـمـسـمـوح {SONG_DOWNLOAD_DURATION} دقـيـقـة")
        
        # جلب الأزرار الأساسية (صوت / فيديو)
        buttons = song_markup(None, vidid)
        await mystic.delete()
        
        await message.reply_photo(
            photo=thumbnail, 
            caption=f"الـعـنـوان: {title}\nالـمـدة: {duration_min}\n\nاخـتـر نـوع الـمـلـف الـمـطـلـوب:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        await mystic.edit_text("لـم يـتـم الـعـثـور عـلى نـتـائج")

@app.on_message(filters.command(["يوت"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_direct_processor(client, message: Message):
    """أمر يوت للتحميل المباشر بأعلى جودة صوت MP3"""
    if len(message.command) < 2:
        return await message.reply_text("يـرجى كـتـابـة الاسـم بـعـد الأمـر")
    
    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("جـاري الـتـنـزيـل")
    
    try:
        title, _, duration_sec, _, vidid = await YouTube.details(query)
        # التحميل عبر المحرك النووي بـ 16 اتصال متوازي
        file_path, direct = await YouTube.download(f"https://www.youtube.com/watch?v={vidid}", mystic, songaudio=True)
        
        await mystic.edit_text("جـاري الـرف_ع")
        # الإرسال عبر دالة المحرك النووية لدعم الرفع حتى 2 جيجا
        await YouTube.send_nuclear_file(
            client, message.chat.id, file_path, direct, False, 
            title, duration_sec, None, message.from_user.first_name
        )
        await mystic.delete()
    except Exception:
        await mystic.edit_text("حـدث خـطأ في الـنـظام")

@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS)
async def song_helper_callback(client, CallbackQuery):
    """جلب قائمة الجودات المطولة (التي تولدها دالة get_quality_buttons في المحرك)"""
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جـاري الـتـحـضـيـر")
    
    # استدعاء الجودات المتاحة بنسق مطول من المحرك المركزي
    buttons = await YouTube.get_quality_buttons(vidid, stype)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
async def song_download_callback(client, CallbackQuery):
    """التنزيل النهائي للملف المختار (فيديو أو صوت) والرفع من الرام ديسك"""
    stype, format_id, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    mystic = await CallbackQuery.edit_message_text("جـاري الـتـنـزيـل")
    is_video = (stype == "video")
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    
    try:
        # تنفيذ التحميل والدمج (للفيديو) أو التحويل (للصوت) عبر المحرك النووي
        file_path, direct = await YouTube.download(
            yturl, mystic, 
            songvideo=is_video, 
            songaudio=not is_video, 
            format_id=format_id
        )
        
        await mystic.edit_text("جـاري الـرف_ع")
        
        # جلب البيانات النهائية للتأكد من العنوان والمدة
        with yt_dlp.YoutubeDL({"quiet": True}) as ytdl:
            info = ytdl.extract_info(yturl, download=False)
        
        thumb = await CallbackQuery.message.download() if CallbackQuery.message.photo else None
        
        # الرفع النووي النهائي مع التنظيف الآلي للرام ديسك
        await YouTube.send_nuclear_file(
            client, CallbackQuery.message.chat.id, file_path, direct, 
            is_video, info.get("title"), info.get("duration", 0), 
            thumb, CallbackQuery.from_user.first_name
        )
        await mystic.delete()
    except Exception:
        await mystic.edit_text("فـشل إرسـال الـمـلـف")

@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS)
async def song_back_callback(client, CallbackQuery):
    """الرجوع للقائمة الرئيسية للاختيار"""
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    buttons = song_markup(None, vidid)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
