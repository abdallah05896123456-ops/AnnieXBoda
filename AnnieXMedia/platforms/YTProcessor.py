# System: Processor | Anti-Bot Bypass | Force JPG Thumb | Smart Retry | RAM Disk

import asyncio
import os
import time
import random
import glob
import shutil
import yt_dlp
from concurrent.futures import ThreadPoolExecutor
from pyrogram.types import InputMediaAudio, InputMediaVideo, InlineKeyboardButton
from pyrogram.errors import MessageIdInvalid, MessageNotModified
from config import LOGGER_ID
from AnnieXMedia import LOGGER
from AnnieXMedia.utils.formatters import convert_bytes

class Config:
    # استخدام الرام ديسك للسرعة القصوى
    DOWNLOAD_PATH = "/dev/shm/AnnieDownloads" if os.path.exists("/dev/shm") else "downloads"
    # User-Agent حديث جداً لتجاوز الحظر
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    MAX_WORKERS = 16 

if not os.path.exists(Config.DOWNLOAD_PATH):
    os.makedirs(Config.DOWNLOAD_PATH, exist_ok=True)

class YTProcessorAPI:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)
        self._clean_cache()

    def _clean_cache(self):
        try:
            for filename in os.listdir(Config.DOWNLOAD_PATH):
                file_path = os.path.join(Config.DOWNLOAD_PATH, filename)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
        except Exception:
            pass

    def get_cookie_file(self):
        # البحث عن ملف الكوكيز في المسار الرئيسي
        if os.path.exists("cookies.txt") and os.path.getsize("cookies.txt") > 0:
            return "cookies.txt"
        return None

    async def get_quality_buttons(self, vidid, stype):
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        cookie_file = self.get_cookie_file()
        
        # خيارات استخراج المعلومات (سريعة)
        ydl_opts = {
            "quiet": True,
            "cookiefile": cookie_file,
            "user_agent": Config.USER_AGENT,
            "no_warnings": True,
            "ignoreerrors": True,
        }
        
        loop = asyncio.get_running_loop()
        
        # محاولة أولى: Web Client
        def _fetch_web():
            opts = ydl_opts.copy()
            opts['extractor_args'] = {'youtube': {'player_client': ['web']}}
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(yturl, download=False)

        # محاولة ثانية: Android Client (لتجاوز تسجيل الدخول)
        def _fetch_android():
            opts = ydl_opts.copy()
            opts['extractor_args'] = {'youtube': {'player_client': ['android']}}
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(yturl, download=False)

        formats = []
        try:
            info = await loop.run_in_executor(self.pool, _fetch_web)
            formats = info.get("formats", [])
        except:
            try:
                info = await loop.run_in_executor(self.pool, _fetch_android)
                formats = info.get("formats", [])
            except:
                pass 

        keyboard = []
        if stype == "audio":
            keyboard.append([InlineKeyboardButton(text="جـودة فـائـقـة (320)", callback_data=f"song_download audio|high|{vidid}")])
            keyboard.append([InlineKeyboardButton(text="جـودة مـتـوسـطـة (128)", callback_data=f"song_download audio|mid|{vidid}")])
            keyboard.append([InlineKeyboardButton(text="جـودة مـنـخـفـضـة", callback_data=f"song_download audio|low|{vidid}")])
        else:
            has_high = False
            if formats:
                for x in formats:
                    h = x.get("height")
                    if h and h >= 1080: has_high = True

            if has_high:
                keyboard.append([InlineKeyboardButton(text="جـودة فـائـقـة (4K/1080)", callback_data=f"song_download video|high|{vidid}")])
            keyboard.append([InlineKeyboardButton(text="جـودة مـتـوسـطـة (720/480)", callback_data=f"song_download video|mid|{vidid}")])
            keyboard.append([InlineKeyboardButton(text="جـودة مـنـخـفـضـة (360/144)", callback_data=f"song_download video|low|{vidid}")])
        
        keyboard.append([InlineKeyboardButton(text="إغـلاق", callback_data="close")])
        return keyboard

    async def download_file(self, url, quality_arg, is_video, title, vidid=None, is_owner=False):
        vid_id_str = vidid if vidid else str(int(time.time()))
        ext = "mp4" if is_video else "mp3"
        final_file = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.{ext}")
        
        # كاش الرام
        if os.path.exists(final_file) and os.path.getsize(final_file) > 1024:
            return final_file

        cookie_file = self.get_cookie_file()
        if not url.startswith("http"): url = f"ytsearch1:{url}"

        # إعدادات التحميل الأساسية
        base_opts = {
            "outtmpl": os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.%(ext)s"),
            "user_agent": Config.USER_AGENT,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "nocheckcertificate": True,
            # إعدادات Aria2c السريعة
            "external_downloader": "aria2c",
            "external_downloader_args": [
                "-x", "16", "-s", "16", "-k", "1M", 
                "--max-connection-per-server=16", 
                "--file-allocation=none"
            ],
            "writethumbnail": True, 
            "socket_timeout": 60,
            "retries": 10,
        }
        
        # --- تحديد الجودة ---
        if is_video:
            if quality_arg == "high" or (is_owner and quality_arg == "best"):
                fmt = "bestvideo+bestaudio/best"
            elif quality_arg == "mid":
                fmt = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
            elif quality_arg == "low":
                fmt = "bestvideo[height<=360]+bestaudio/best[height<=360]/best"
            else:
                fmt = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
        else:
            if is_owner or quality_arg == "high":
                fmt = "bestaudio/best"
                q_rate = '320'
            elif quality_arg == "low":
                fmt = "bestaudio/best"
                q_rate = '64'
            else:
                fmt = "bestaudio/best"
                q_rate = '128'

            base_opts["postprocessors"] = [
                {'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': q_rate},
                {'key': 'FFmpegMetadata', 'add_metadata': True},
                {'key': 'EmbedThumbnail'},
                {'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'} # إجبار تحويل الغلاف لـ JPG
            ]

        loop = asyncio.get_running_loop()

        # دالة التشغيل التي تعيد المحاولة تلقائياً مع عملاء مختلفين
        def _smart_download():
            # المحاولة 1: Web Client (الأسرع والأفضل للجودة)
            try:
                opts = base_opts.copy()
                opts['format'] = fmt
                opts['cookiefile'] = cookie_file
                opts['extractor_args'] = {'youtube': {'player_client': ['web']}}
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                if os.path.exists(final_file): return final_file
            except:
                pass

            # المحاولة 2: Android Client (يتجاوز حظر البوت وتسجيل الدخول)
            try:
                opts = base_opts.copy()
                opts['format'] = fmt
                opts['cookiefile'] = cookie_file # نجرب بالكوكيز أيضاً
                opts['extractor_args'] = {'youtube': {'player_client': ['android']}}
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                if os.path.exists(final_file): return final_file
            except:
                pass
            
            # المحاولة 3: iOS Client (ملاذ أخير)
            try:
                opts = base_opts.copy()
                opts['format'] = fmt
                opts['cookiefile'] = None # بدون كوكيز
                opts['extractor_args'] = {'youtube': {'player_client': ['ios']}}
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                if os.path.exists(final_file): return final_file
            except:
                pass
            
            return None

        result_path = await loop.run_in_executor(self.pool, _smart_download)
        return result_path

    async def upload_alexa_style(self, client, mystic_msg, file_path, is_video, title, duration, user_name, vidid=None):
        if not file_path or not os.path.exists(file_path):
            return False

        caption = f"**الـعـنـوان:** {title}\n**طـلـب:** {user_name}"
        chat_id = mystic_msg.chat.id
        
        # --- البحث الدقيق عن الغلاف ---
        thumb_path = None
        base_name = os.path.splitext(file_path)[0]
        
        # 1. البحث بنفس اسم الملف (الأدق)
        for ext in [".jpg", ".jpeg", ".png"]: # تجاهلنا webp لأن تيليجرام لا يحبه كغلاف
            if os.path.exists(f"{base_name}{ext}"):
                thumb_path = f"{base_name}{ext}"
                break
        
        # 2. البحث بالـ ID إذا فشل الاسم
        if not thumb_path and vidid:
             possible_files = glob.glob(os.path.join(Config.DOWNLOAD_PATH, f"*{vidid}*"))
             for f in possible_files:
                if f.endswith((".jpg", ".jpeg", ".png")) and not f.endswith((".mp3", ".mp4", ".mkv")):
                    thumb_path = f
                    break
        # -----------------------------

        # محاولة الرفع مع معالجة خطأ MessageIdInvalid
        try:
            # محاولة التعديل أولاً (أسرع)
            if is_video:
                media = InputMediaVideo(media=file_path, thumb=thumb_path, caption=caption, duration=duration, supports_streaming=True)
            else:
                media = InputMediaAudio(media=file_path, thumb=thumb_path, caption=caption, duration=duration, title=title, performer=user_name)
            
            await mystic_msg.edit_media(media=media)
            
        except (MessageIdInvalid, MessageNotModified):
            # إذا فشل التعديل (الرسالة قديمة أو محذوفة)، نرسل رسالة جديدة
            try:
                # نحاول حذف رسالة الانتظار القديمة
                try: await mystic_msg.delete()
                except: pass
                
                if is_video:
                    await client.send_video(chat_id, video=file_path, caption=caption, duration=duration, thumb=thumb_path, supports_streaming=True)
                else:
                    await client.send_audio(chat_id, audio=file_path, caption=caption, duration=duration, title=title, performer=user_name, thumb=thumb_path)
            except Exception as e:
                print(f"Upload Failed: {e}")
                return False
        except Exception as e:
            # أي خطأ آخر، نحاول الإرسال الجديد أيضاً
            try:
                if is_video:
                    await client.send_video(chat_id, video=file_path, caption=caption, duration=duration, thumb=thumb_path)
                else:
                    await client.send_audio(chat_id, audio=file_path, caption=caption, duration=duration, title=title, performer=user_name, thumb=thumb_path)
            except:
                return False
        
        return True

Processor = YTProcessorAPI()
