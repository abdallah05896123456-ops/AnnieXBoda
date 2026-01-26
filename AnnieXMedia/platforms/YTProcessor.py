# System: Processor | NUCLEAR EDITION (16-Core) | RAM Disk | Client Rotation | Remote Fix

import asyncio
import os
import time
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
    # استخدام الرامات (RAM Disk) للتخزين المؤقت للسرعة القصوى
    if os.path.exists("/dev/shm"):
        DOWNLOAD_PATH = "/dev/shm/AnnieDownloads"
    else:
        DOWNLOAD_PATH = os.path.abspath("downloads")
        
    # استغلال 16 نواة
    MAX_WORKERS = 16 
    
    # User-Agent يحاكي متصفح حقيقي لتجنب الحظر
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

# انشاء المجلد
if not os.path.exists(Config.DOWNLOAD_PATH):
    os.makedirs(Config.DOWNLOAD_PATH, exist_ok=True)

class YTProcessorAPI:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)
        self._clean_cache()

    def _clean_cache(self):
        """تنظيف الكاش عند البدء"""
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
        """البحث عن الكوكيز في جميع المسارات المحتملة"""
        possible_paths = [
            "cookies.txt", 
            "AnnieXMedia/assets/cookies.txt",
            "AnnieXMedia/cookies.txt", 
            "assets/cookies.txt", 
            "platforms/cookies.txt"
        ]
        for path in possible_paths:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return path
        return None

    async def get_quality_buttons(self, vidid, stype):
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        cookie_file = self.get_cookie_file()
        
        ydl_opts = {
            "quiet": True,
            "cookiefile": cookie_file,
            "no_warnings": True,
            "ignoreerrors": True,
            "nocheckcertificate": True,
            "remote_components": ["ejs:github"], # اضافة الريموت لتحديث الاكواد
        }
        
        loop = asyncio.get_running_loop()
        
        def _fetch_info():
            # محاولة سريعة باستخدام الويب
            try:
                opts = ydl_opts.copy()
                opts['extractor_args'] = {'youtube': {'player_client': ['web']}}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(yturl, download=False)
            except:
                return None

        formats = []
        try:
            info = await loop.run_in_executor(self.pool, _fetch_info)
            if info: formats = info.get("formats", [])
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
        ext = "mp4" if is_video else "m4a" 
        final_file = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.{ext}")
        
        # فحص الكاش
        if os.path.exists(final_file) and os.path.getsize(final_file) > 1024:
            return final_file

        cookie_file = self.get_cookie_file()
        if not url.startswith("http"): url = f"https://www.youtube.com/watch?v={vidid}"

        # --- إعدادات Aria2c النووية (16 كور) ---
        aria2_args = [
            "-x", "16", "-s", "16", "-j", "16", "-k", "1M",
            "--file-allocation=none", 
            "--disable-ipv6=true",
            "--max-connection-per-server=16"
        ]

        base_opts = {
            "outtmpl": os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.%(ext)s"),
            "cookiefile": cookie_file,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "quiet": True,
            "noplaylist": True,
            "external_downloader": "aria2c",
            "external_downloader_args": aria2_args,
            "writethumbnail": True,
            "socket_timeout": 60,
            "retries": 10,
            # إضافة الريموت لحل مشاكل التوقيع والحظر
            "remote_components": ["ejs:github"],
        }
        
        # --- تحديد الجودة ---
        if is_video:
            if quality_arg == "high" or (is_owner and quality_arg == "best"):
                fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            elif quality_arg == "mid":
                fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best"
            elif quality_arg == "low":
                fmt = "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best"
            else:
                fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best"
        else:
            if is_owner or quality_arg == "high":
                fmt = "bestaudio[ext=m4a]/bestaudio/best"
                q_rate = '320'
            elif quality_arg == "low":
                fmt = "bestaudio[ext=m4a]/bestaudio/best"
                q_rate = '64'
            else:
                fmt = "bestaudio[ext=m4a]/bestaudio/best"
                q_rate = '128'

            base_opts["postprocessors"] = [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': q_rate
                },
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True
                },
                {
                    'key': 'EmbedThumbnail'
                },
                # تحويل الغلاف لـ JPG اجباريا
                {
                    'key': 'FFmpegThumbnailsConvertor',
                    'format': 'jpg'
                }
            ]

        if not is_video:
            final_file = final_file.replace(".m4a", ".mp3")

        base_opts['format'] = fmt

        loop = asyncio.get_running_loop()

        # --- دالة التحميل الذكية (Client Rotation + Remote) ---
        def _run_download_with_rotation():
            # الترتيب: ويب (الافضل جودة) -> اندرويد (تجاوز) -> اي او اس
            clients = ['web', 'android', 'ios', 'tv_embedded']
            
            for client in clients:
                try:
                    opts = base_opts.copy()
                    opts['extractor_args'] = {'youtube': {'player_client': [client]}}
                    
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([url])
                    
                    if os.path.exists(final_file) and os.path.getsize(final_file) > 100:
                        return final_file
                except Exception as e:
                    print(f"Failed with client {client}: {e}")
                    continue
            return None

        return await loop.run_in_executor(self.pool, _run_download_with_rotation)

    async def upload_alexa_style(self, client, mystic_msg, file_path, is_video, title, duration, user_name, vidid=None):
        if not file_path or not os.path.exists(file_path):
            return False

        caption = f"**الـعـنـوان:** {title}\n**طـلـب:** {user_name}"
        chat_id = mystic_msg.chat.id
        
        # --- استراتيجية الغلاف المضمونة ---
        thumb_path = None
        base_name = os.path.splitext(file_path)[0]
        
        # 1. البحث عن ملف الـ JPG الناتج عن FFmpeg
        if os.path.exists(f"{base_name}.jpg"):
            thumb_path = f"{base_name}.jpg"
        
        # 2. محاولة احتياطية
        elif vidid:
             possible_files = glob.glob(os.path.join(Config.DOWNLOAD_PATH, f"*{vidid}*"))
             for f in possible_files:
                if f.endswith((".jpg", ".jpeg", ".png")) and not f.endswith((".mp3", ".mp4", ".m4a", ".mkv")):
                    thumb_path = f
                    break

        try:
            if is_video:
                media = InputMediaVideo(media=file_path, thumb=thumb_path, caption=caption, duration=duration, supports_streaming=True)
            else:
                media = InputMediaAudio(media=file_path, thumb=thumb_path, caption=caption, duration=duration, title=title, performer=user_name)
            
            await mystic_msg.edit_media(media=media)
            
        except (MessageIdInvalid, MessageNotModified):
            # محاولة ارسال رسالة جديدة في حالة فشل التعديل
            try:
                try: await mystic_msg.delete()
                except: pass
                
                if is_video:
                    await client.send_video(chat_id, video=file_path, caption=caption, duration=duration, thumb=thumb_path, supports_streaming=True)
                else:
                    await client.send_audio(chat_id, audio=file_path, caption=caption, duration=duration, title=title, performer=user_name, thumb=thumb_path)
            except:
                return False
        except Exception:
            try:
                if is_video:
                    await client.send_video(chat_id, video=file_path, caption=caption, duration=duration)
                else:
                    await client.send_audio(chat_id, audio=file_path, caption=caption, duration=duration, title=title, performer=user_name)
            except:
                return False
        
        return True

Processor = YTProcessorAPI()
