# Authored By Certified Coders © 2026
# System: Song Plugin | Direct Stream Pipe | Quality Control | Logger
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
    OWNER_ID, 
    MONGO_DB_URI,
    LOGGER_ID
)
from AnnieXMedia import app
from AnnieXMedia.platforms.Youtube import YouTube 
from AnnieXMedia.platforms.YTProcessor import Processor 

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
# أوامر التحكم في الكيبورد والبحث
# ==========================================================

@app.on_message(filters.command(["تفعيل", "فعل كيب البحث"], prefixes=["", "/"]) & filters.user(SUDO_USERS))
async def enable_quality_keyboard(client, message):
    await set_config("keyboard_enabled", True)
    await message.reply_text("تم تفعيل كيبورد اختيار الجودة")

@app.on_message(filters.command(["قفل", "اغلاق كيب البحث"], prefixes=["", "/"]) & filters.user(SUDO_USERS))
async def disable_quality_keyboard(client, message):
    await set_config("keyboard_enabled", False)
    await message.reply_text("تم اغلاق كيبورد اختيار الجودة")

@app.on_message(filters.command(["قفل التنزيل", "تعطيل التنزيل"], prefixes=["", "/"]) & filters.user(SUDO_USERS))
async def lock_download(client, message):
    await set_config("download_locked", True)
    await message.reply_text("تم قفل التنزيل")

@app.on_message(filters.command(["فتح التنزيل", "تفعيل التنزيل"], prefixes=["", "/"]) & filters.user(SUDO_USERS))
async def unlock_download(client, message):
    await set_config("download_locked", False)
    await message.reply_text("تم فتح التنزيل")

# ==========================================================
# دوال مساعدة (الأزرار والكابشن)
# ==========================================================

# زر المالك الثابت
OWNER_BUTTON = InlineKeyboardButton("الـمـالـك", url="https://t.me/S_G0C7")

def get_buttons(vidid):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("فـائـقـة", callback_data=f"song_dl video|high|{vidid}"),
            InlineKeyboardButton("مـتـوسـطـة", callback_data=f"song_dl video|mid|{vidid}"),
            InlineKeyboardButton("مـنـخـفـضـة", callback_data=f"song_dl video|low|{vidid}"),
        ],
        [
            InlineKeyboardButton("فـائـقـة (صوت)", callback_data=f"song_dl audio|high|{vidid}"),
            InlineKeyboardButton("مـتـوسـطـة (صوت)", callback_data=f"song_dl audio|mid|{vidid}"),
            InlineKeyboardButton("مـنـخـفـضـة (صوت)", callback_data=f"song_dl audio|low|{vidid}"),
        ],
        [OWNER_BUTTON], # زر المالك هنا
        [InlineKeyboardButton("إغـلاق", callback_data="close")]
    ])

def get_final_markup():
    # أزرار الرسالة النهائية (المالك فقط)
    return InlineKeyboardMarkup([[OWNER_BUTTON]])

def format_caption(user, title):
    # تنسيق الكابشن المطلوب
    return (
        f"BY ↠ [{user.first_name}](tg://user?id={user.id})\n"
        f"address ↠ {title}"
    )

async def send_to_logger(client, user, title, link, quality, type_str):
    if not LOGGER_ID: return
    text = (
        f"**New Download Log**\n\n"
        f"**User:** {user.mention} [`{user.id}`]\n"
        f"**Title:** {title}\n"
        f"**Link:** {link}\n"
        f"**Type:** {type_str}\n"
        f"**Quality:** {quality}"
    )
    try: await client.send_message(LOGGER_ID, text)
    except: pass

# ==========================================================
# محرك البحث الرئيسي
# ==========================================================

@app.on_message(filters.regex(r"^/?(اغنية|اغنيه|هات|هاتلي|ابعتلي|song|video|تحميل|يوتيوب)(?:\s+(فيد|فيديو|video))?(?:\s+(.+))?$") & ~BANNED_USERS, group=5)
async def song_search_handler(client, message: Message):
    
    if await get_config("download_locked") and message.from_user.id not in SUDO_USERS:
        return await message.reply_text("عـذراً التنزيـل مغلـق مـؤقتـا .")

    match = re.match(r"^/?(اغنية|اغنيه|هات|هاتلي|ابعتلي|song|video|تحميل|يوتيوب)(?:\s+(فيد|فيديو|video))?(?:\s+(.+))?$", message.text)
    if not match: return
    
    video_trigger = match.group(2)
    query = match.group(3)
    is_video_req = match.group(1).lower() in ["video", "/video", "فيديو"] or video_trigger

    if not query:
        return await message.reply_text("ارسل اسم الاغنية")

    mystic = await message.reply_text("جـارٍ الـبـحـث...")

    if "list=" in query:
        return await Processor.download_playlist(client, mystic, query, is_video_req, message.from_user.first_name)

    try:
        (
            title,
            duration_min,
            duration_sec,
            thumbnail,
            vidid,
        ) = await YouTube.details(query)

        if str(duration_min) == "None":
            return await mystic.edit_text("لم يتم العثور على نتائج")
            
        if int(duration_sec) > 14400: 
            return await mystic.edit_text("المقطع طويل جدا")
        
        await mystic.delete()
        
        # استخدام دالة التنسيق الجديدة
        caption = format_caption(message.from_user, title)
        
        # فحص تفعيل الكيبورد
        if await get_config("keyboard_enabled"):
            await message.reply_photo(
                thumbnail,
                caption=caption,
                reply_markup=get_buttons(vidid)
            )
        else:
            # التحميل المباشر (تلقائي متوسط)
            stype = "video" if is_video_req else "audio"
            quality = "high" if message.from_user.id in SUDO_USERS else "mid"
            
            # محاكاة زر الضغط
            class MockCallback:
                def __init__(self):
                    self.message = message
                    self.from_user = message.from_user
                    self.data = f"song_dl {stype}|{quality}|{vidid}"
                async def answer(self, *args, **kwargs): pass
                async def edit_message_text(self, text): return await message.reply_text(text)
                
            await song_download_callback(client, MockCallback())

    except Exception as e:
        await mystic.edit_text("حدث خطأ أثناء البحث")

# ==========================================================
# معالج التحميل (The Engine)
# ==========================================================

@app.on_callback_query(filters.regex(pattern=r"song_dl") & ~BANNED_USERS)
async def song_download_callback(client, CallbackQuery):
    data = CallbackQuery.data.split(None, 1)[1]
    stype, quality_arg, vidid = data.split("|")
    
    is_video = (stype == "video")
    user_id = CallbackQuery.from_user.id
    is_owner = user_id in SUDO_USERS
    
    # تحديد الجودة الفعلية (المالك: قصوى، العضو: متوسطة إجبارية)
    if not is_owner and quality_arg == "high": quality_arg = "mid"
    
    await CallbackQuery.answer("جاري التحميل...", cache_time=0)
    
    try:
        mystic = await CallbackQuery.edit_message_text("جـارٍ الـتـحـمـيـل...")
    except:
        mystic = await client.send_message(CallbackQuery.message.chat.id, "جـارٍ الـتـحـمـيـل...")
    
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    
    try:
        # 1. جلب المعلومات
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(yturl, download=False)
            
        title = info.get("title", "Unknown")
        title = re.sub(r'[\\/*?:"<>|]', "", title) # تنظيف الاسم للملف
        display_title = info.get("title", "Unknown") # العنوان للعرض (يحتوي رموز عادي)
        duration = info.get("duration", 0)
        
        # 2. اللوجر
        await send_to_logger(client, CallbackQuery.from_user, display_title, yturl, quality_arg, stype)

        # 3. محاولة البث المباشر (Piping) للأغاني الفردية
        # نستخدم YTProcessor الجديد الذي يحتوي على الدالة بداخله
        stream_path = await Processor.download_file(
            yturl, quality_arg, is_video, title, vidid=vidid, is_owner=is_owner
        )
        
        if not stream_path:
             return await mystic.edit_text("فشل استخراج الرابط")

        # 4. الرفع
        await mystic.edit_text("جـارٍ الـرفـع...")
        
        # تنزيل الغلاف محلياً للدمج
        thumb_path = f"downloads/{vidid}.jpg"
        if not os.path.exists(thumb_path):
            await asyncio.create_subprocess_shell(f"wget -q -O {thumb_path} {info['thumbnail']}")

        # الكابشن النهائي عند الرفع
        caption = format_caption(CallbackQuery.from_user, display_title)
        
        # أزرار الرسالة النهائية (المالك)
        final_markup = get_final_markup()

        if is_video:
            media = InputMediaVideo(
                media=stream_path,
                duration=duration,
                thumb=thumb_path,
                caption=caption,
                supports_streaming=True
            )
            action = enums.ChatAction.UPLOAD_VIDEO
        else:
            media = InputMediaAudio(
                media=stream_path,
                caption=caption,
                thumb=thumb_path,
                title=display_title,
                performer="Annie Music",
                file_name=f"{title}.mp3" # اسم الملف عند التنزيل
            )
            action = enums.ChatAction.UPLOAD_AUDIO
            
        await client.send_chat_action(CallbackQuery.message.chat.id, action)
        
        # استخدام edit_media لو الرسالة موجودة، أو send لو جديدة
        if isinstance(mystic, Message):
            try: 
                await mystic.edit_media(media=media, reply_markup=final_markup)
            except: 
                # في حالة فشل التعديل (مثلا تغير النوع من نص لميديا)
                await mystic.delete()
                if is_video: 
                    await client.send_video(CallbackQuery.message.chat.id, video=stream_path, caption=caption, duration=duration, thumb=thumb_path, reply_markup=final_markup)
                else: 
                    await client.send_audio(CallbackQuery.message.chat.id, audio=stream_path, caption=caption, duration=duration, thumb=thumb_path, title=display_title, performer="Annie Music", file_name=f"{title}.mp3", reply_markup=final_markup)
        
    except Exception as e:
        await mystic.edit_text(f"خطأ: {e}")
        
    finally:
        if 'stream_path' in locals() and os.path.exists(stream_path): os.remove(stream_path)
        if 'thumb_path' in locals() and os.path.exists(thumb_path): os.remove(thumb_path)

@app.on_callback_query(filters.regex("close"))
async def close_cb(_, query):
    await query.message.delete()
