# Authored By Certified Coders © 2026
# System: Song Plugin | Direct Stream Pipe | Quality Control | Logger
# Optimized for AnnieXMedia Bot Folder Structure

import asyncio
import os
import re
import yt_dlp
import aiohttp
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

# --- إدارة الإعدادات ---
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
# أوامر التحكم (للمطورين فقط)
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
# دوال مساعدة (الأزرار والكابشن واللوجر)
# ==========================================================

# زر المالك الثابت
OWNER_BUTTON = InlineKeyboardButton("الـمـالـك", url="https://t.me/S_G0C7")

def get_buttons(vidid):
    # أزرار ثابتة لاختيار الجودة مباشرة (تخطي مرحلة الجلب)
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
        [OWNER_BUTTON],
        [InlineKeyboardButton("إغـلاق", callback_data="close")]
    ])

def get_final_markup():
    return InlineKeyboardMarkup([[OWNER_BUTTON]])

def format_caption(user, title):
    return (
        f"BY ↠ [{user.first_name}](tg://user?id={user.id})\n"
        f"address ↠ {title}"
    )

async def download_thumb_locally(url, path):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    with open(path, 'wb') as f:
                        f.write(await resp.read())
                    return True
    except: pass
    return False

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
# أمر (يوت) للتحميل الصوتي المباشر
# ==========================================================

@app.on_message(filters.command(["يوت", "yt"], prefixes=["", "/"]) & ~BANNED_USERS)
async def direct_yot_audio(client, message: Message):
    if await get_config("download_locked") and message.from_user.id not in SUDO_USERS:
        return await message.reply_text("عـذراً التنزيـل مغلـق مـؤقتـا .")

    if len(message.command) < 2:
        return await message.reply_text("ضع رابط او اسم الاغنية بجانب الامر")
    
    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("جـارٍ الـمـعـالـجـة...")
    
    try:
        # جلب المعلومات
        (title, duration_min, duration, thumbnail, vidid) = await YouTube.details(query)
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        
        # تحديد الجودة (متوسطة للأعضاء، عالية للمالك)
        quality = "high" if message.from_user.id in SUDO_USERS else "mid"
        
        # بدء التنزيل (Piping)
        stream_path = await Processor.download_file(
            yturl, quality, False, title, vidid=vidid, is_owner=(message.from_user.id in SUDO_USERS)
        )
        
        if not stream_path:
            return await mystic.edit_text("فشل التحميل")
            
        await mystic.edit_text("جـارٍ الـرفـع...")
        
        # تحميل الغلاف
        thumb_path = f"downloads/{vidid}.jpg"
        if not os.path.exists(thumb_path):
            await download_thumb_locally(thumbnail, thumb_path)
            
        caption = format_caption(message.from_user, title)
        
        # تعديل اسم الملف
        final_path = stream_path
        safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
        if safe_title:
            new_path = f"downloads/{safe_title}.mp3"
            try:
                if os.path.exists(stream_path):
                    os.rename(stream_path, new_path)
                    final_path = new_path
            except: pass

        # الرفع
        await client.send_chat_action(message.chat.id, enums.ChatAction.UPLOAD_AUDIO)
        
        await client.send_audio(
            message.chat.id,
            audio=final_path,
            caption=caption,
            duration=int(duration) if duration else 0,
            thumb=thumb_path,
            title=title,
            performer="Annie Music",
            reply_markup=get_final_markup()
        )
        
        await mystic.delete()
        
        # اللوجر
        await send_to_logger(client, message.from_user, title, yturl, quality, "audio (Yout)")

    except Exception as e:
        await mystic.edit_text(f"خطأ: {e}")
        
    finally:
        if 'final_path' in locals() and os.path.exists(final_path): try: os.remove(final_path)
        except: pass
        if 'stream_path' in locals() and os.path.exists(stream_path): try: os.remove(stream_path)
        except: pass
        if 'thumb_path' in locals() and os.path.exists(thumb_path): try: os.remove(thumb_path)
        except: pass

# ==========================================================
# محرك البحث الرئيسي
# ==========================================================

@app.on_message(filters.regex(r"^/?(اغنية|اغنيه|هات|هاتلي|ابعتلي|song|video|تحميل|يوتيوب)(?:\s+(فيد|فيديو|video))?(?:\s+(.+))?$") & ~BANNED_USERS, group=5)
async def song_search_handler(client, message: Message):
    
    # التحقق من قفل التنزيل
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

    # دعم القوائم (يتم تحويله للمعالج الخاص)
    if "list=" in query:
        return await Processor.download_playlist(client, mystic, query, is_video_req, message.from_user.first_name)

    try:
        # جلب المعلومات الأساسية
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
        
        caption = format_caption(message.from_user, title)
        
        # التحقق من حالة الكيبورد (مفعل/مغلق)
        if await get_config("keyboard_enabled"):
            # الكيبورد مفعل: عرض الخيارات
            await message.reply_photo(
                thumbnail,
                caption=caption,
                reply_markup=get_buttons(vidid)
            )
        else:
            # الكيبورد مغلق: تحميل مباشر (تلقائي)
            # تحديد النوع والجودة
            stype = "video" if is_video_req else "audio"
            # المالك = عالية، العضو = متوسطة
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
    
    # --- منطق تقييد الجودة ---
    # إذا لم يكن المالك وطلب جودة عالية -> نحولها لمتوسطة
    if not is_owner and quality_arg == "high": 
        quality_arg = "mid"
    
    await CallbackQuery.answer("جاري التحميل...", cache_time=0)
    
    try:
        mystic = await CallbackQuery.edit_message_text("جـارٍ الـتـحـمـيـل...")
    except:
        mystic = await client.send_message(CallbackQuery.message.chat.id, "جـارٍ الـتـحـمـيـل...")
    
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    
    try:
        # 1. جلب المعلومات الدقيقة (عشان الاسم واللوجر)
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(yturl, download=False)
            
        # تنظيف العنوان ليكون صالحاً كاسم ملف
        title = info.get("title", "Unknown")
        safe_title = re.sub(r'[\\/*?:"<>|]', "", title) 
        display_title = title # العنوان للعرض
        duration = info.get("duration", 0)
        
        # 2. إرسال السجل (Logger)
        await send_to_logger(client, CallbackQuery.from_user, display_title, yturl, quality_arg, stype)

        # 3. بدء التنزيل (استخدام Processor مع Piping)
        # نمرر is_owner للتحكم في Aria2c لو لزم الأمر (لكن هنا الأغاني الفردية piping)
        stream_path = await Processor.download_file(
            yturl, quality_arg, is_video, safe_title, vidid=vidid, is_owner=is_owner
        )
        
        if not stream_path:
             return await mystic.edit_text("فشل استخراج الرابط")

        # 4. الرفع
        await mystic.edit_text("جـارٍ الـرفـع...")
        
        # تحميل الغلاف محلياً (باستخدام aiohttp لتجنب wget)
        thumb_path = f"downloads/{vidid}.jpg"
        if not os.path.exists(thumb_path):
            await download_thumb_locally(info['thumbnail'], thumb_path)

        # تجهيز الكابشن والزر النهائي
        caption = format_caption(CallbackQuery.from_user, display_title)
        final_markup = get_final_markup()

        # 5. تعديل اسم الملف (Rename) ليظهر باسم الأغنية عند المستخدم
        final_path = stream_path
        if safe_title:
            ext = ".mp4" if is_video else ".mp3"
            new_path = f"downloads/{safe_title}{ext}"
            try:
                # إذا كان Stream Path أنبوب (FIFO)، التسمية لا تهم كثيراً للبايثون
                # لكن للتيليجرام file_name هو المهم
                if os.path.exists(stream_path):
                    os.rename(stream_path, new_path)
                    final_path = new_path
            except:
                pass

        if is_video:
            media = InputMediaVideo(
                media=final_path,
                duration=duration,
                thumb=thumb_path,
                caption=caption,
                supports_streaming=True
            )
            action = enums.ChatAction.UPLOAD_VIDEO
        else:
            media = InputMediaAudio(
                media=final_path,
                caption=caption,
                thumb=thumb_path,
                title=display_title,
                performer="Annie Music",
                file_name=f"{safe_title}.mp3" # اسم الملف الفعلي
            )
            action = enums.ChatAction.UPLOAD_AUDIO
            
        await client.send_chat_action(CallbackQuery.message.chat.id, action)
        
        # محاولة التعديل أولاً (Edit Media)
        if isinstance(mystic, Message):
            try: 
                await mystic.edit_media(media=media, reply_markup=final_markup)
            except: 
                # في حالة فشل التعديل (مثلا تغير النوع)، نحذف ونرسل جديد
                await mystic.delete()
                if is_video: 
                    await client.send_video(
                        CallbackQuery.message.chat.id, 
                        video=final_path, 
                        caption=caption, 
                        duration=duration, 
                        thumb=thumb_path, 
                        reply_markup=final_markup,
                        supports_streaming=True
                    )
                else: 
                    await client.send_audio(
                        CallbackQuery.message.chat.id, 
                        audio=final_path, 
                        caption=caption, 
                        duration=duration, 
                        thumb=thumb_path, 
                        title=display_title, 
                        performer="Annie Music", 
                        file_name=f"{safe_title}.mp3", 
                        reply_markup=final_markup
                    )
        
    except Exception as e:
        await mystic.edit_text(f"خطأ: {e}")
        
    finally:
        # تنظيف الملفات (سواء كانت أنبوب أو ملف عادي)
        if 'final_path' in locals() and os.path.exists(final_path): 
            try: os.remove(final_path)
            except: pass
        if 'stream_path' in locals() and os.path.exists(stream_path): 
            try: os.remove(stream_path)
            except: pass
        if 'thumb_path' in locals() and os.path.exists(thumb_path): 
            try: os.remove(thumb_path)
            except: pass

@app.on_callback_query(filters.regex("close"))
async def close_cb(_, query):
    await query.message.delete()
