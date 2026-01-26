# System: Processor | Fix Thumbnails | 3 Quality Levels | No Emojis

import asyncio
import os
import time
import random
import glob
import yt_dlp
from concurrent.futures import ThreadPoolExecutor
from pyrogram.types import InputMediaAudio, InputMediaVideo, InlineKeyboardButton
from config import LOGGER_ID
from AnnieXMedia import LOGGER
from AnnieXMedia.utils.formatters import convert_bytes

class Config:
    DOWNLOAD_PATH = "/dev/shm/AnnieDownloads" if os.path.exists("/dev/shm") else "downloads"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    MAX_WORKERS = 16

if not os.path.exists(Config.DOWNLOAD_PATH):
    os.makedirs(Config.DOWNLOAD_PATH, exist_ok=True)

class YTProcessorAPI:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)

    def get_cookie_file(self):
        paths = ["cookies.txt", "AnnieXMedia/assets/cookies.txt", "assets/cookies.txt", "AnnieXMedia/cookies.txt"]
        if os.path.exists("cookies"):
            for f in os.listdir("cookies"):
                if f.endswith(".txt"): paths.append(os.path.join("cookies", f))
        
        valid = [p for p in paths if os.path.exists(p) and os.path.getsize(p) > 0]
        return random.choice(valid) if valid else None

    async def get_quality_buttons(self, vidid, stype):
        """
        تقسيم الجودات إلى 3 فئات فقط: فائقة، متوسطة، منخفضة
        """
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        cookie_file = self.get_cookie_file()
        
        ydl_opts = {
            "quiet": True,
            "cookiefile": cookie_file,
            "user_agent": Config.USER_AGENT,
            "remote_components": ["ejs:github"],
            "nocheckcertificate": True,
            "extractor_args": {"youtube": {"player_client": ["web"]}} 
        }
        
        loop = asyncio.get_running_loop()
        def _fetch():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(yturl, download=False)
        
        formats = []
        try:
            info = await loop.run_in_executor(self.pool, _fetch)
            formats = info.get("formats", [])
        except:
            try:
                ydl_opts["extractor_args"] = {"youtube": {"player_client": ["android"]}}
                ydl_opts["cookiefile"] = None
                info = await loop.run_in_executor(self.pool, _fetch)
                formats = info.get("formats", [])
            except:
                pass 

        keyboard = []
        
        if stype == "audio":
            # للصوت: فائقة (320)، متوسطة (128)، منخفضة (64/48)
            keyboard.append([InlineKeyboardButton(text="جـودة فـائـقـة", callback_data=f"song_download audio|high|{vidid}")])
            keyboard.append([InlineKeyboardButton(text="جـودة مـتـوسـطـة", callback_data=f"song_download audio|mid|{vidid}")])
            keyboard.append([InlineKeyboardButton(text="جـودة مـنـخـفـضـة", callback_data=f"song_download audio|low|{vidid}")])

        else:
            # للفيديو: تحليل الجودات المتاحة لتحديد ما يمكن عرضه
            has_high = False # 1080, 2K, 4K
            has_mid = False  # 720, 480
            has_low = False  # 360, 240, 144
            
            if formats:
                for x in formats:
                    h = x.get("height")
                    if h:
                        if h >= 1080: has_high = True
                        elif 480 <= h <= 720: has_mid = True
                        elif h < 480: has_low = True

            # عرض الأزرار بناءً على التوفر (أو عرض الكل كخيار افتراضي)
            if has_high:
                keyboard.append([InlineKeyboardButton(text="جـودة فـائـقـة (4K/1080)", callback_data=f"song_download video|high|{vidid}")])
            
            # المتوسطة والمنخفضة نعرضهم دائماً لأنهم متاحين غالباً
            keyboard.append([InlineKeyboardButton(text="جـودة مـتـوسـطـة (720/480)", callback_data=f"song_download video|mid|{vidid}")])
            keyboard.append([InlineKeyboardButton(text="جـودة مـنـخـفـضـة (360/144)", callback_data=f"song_download video|low|{vidid}")])
        
        keyboard.append([InlineKeyboardButton(text="إغـلاق", callback_data="close")])
        return keyboard

    async def download_file(self, url, quality_arg, is_video, title, vidid=None, is_owner=False):
        vid_id_str = vidid if vidid else str(int(time.time()))
        ext = "mp4" if is_video else "mp3"
        final_file = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.{ext}")
        
        if os.path.exists(final_file) and os.path.getsize(final_file) > 1024:
            return final_file

        cookie_file = self.get_cookie_file()
        if not url.startswith("http"): url = f"ytsearch1:{url}"

        base_opts = {
            "outtmpl": os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.%(ext)s"),
            "user_agent": Config.USER_AGENT,
            "quiet": True,
            "nocheckcertificate": True,
            "external_downloader": "aria2c",
            "external_downloader_args": ["-x", "16", "-s", "16", "-k", "1M"],
            "writethumbnail": True, # هذا السطر مهم جداً لتحميل الغلاف
        }
        
        if is_video:
            # منطق الجودات الجديد للفيديو
            if quality_arg == "high" or (is_owner and quality_arg == "best"):
                # فائقة: هات أفضل شيء (4K/2K/1080)
                fmt = "bestvideo+bestaudio/best"
            elif quality_arg == "mid":
                # متوسطة: حد أقصى 720
                fmt = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
            elif quality_arg == "low":
                # منخفضة: حد أقصى 360
                fmt = "bestvideo[height<=360]+bestaudio/best[height<=360]/best"
            else:
                # افتراضي
                fmt = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
        else:
            # منطق الجودات الجديد للصوت
            if quality_arg == "high" or is_owner:
                fmt = "bestaudio/best"
                quality = '320'
            elif quality_arg == "mid":
                fmt = "bestaudio/best"
                quality = '128' 
            elif quality_arg == "low":
                fmt = "bestaudio/best"
                quality = '64' # حجم صغير جداً
            else:
                fmt = "bestaudio/best"
                quality = '128'

            base_opts["postprocessors"] = [
                {'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': quality},
                {'key': 'EmbedThumbnail'}, 
                {'key': 'FFmpegMetadata', 'add_metadata': True}
            ]

        opts_1 = base_opts.copy()
        opts_1.update({
            "format": fmt,
            "cookiefile": cookie_file,
            "remote_components": ["ejs:github"],
            "extractor_args": {"youtube": {"player_client": ["web"]}}
        })

        opts_2 = base_opts.copy()
        opts_2.update({
            "format": fmt,
            "cookiefile": None, 
            "extractor_args": {"youtube": {"player_client": ["android"]}}
        })

        loop = asyncio.get_running_loop()
        def _run(opts):
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            return final_file

        try:
            await loop.run_in_executor(self.pool, lambda: _run(opts_1))
        except:
            try:
                await loop.run_in_executor(self.pool, lambda: _run(opts_2))
            except:
                return None

        return final_file

    async def upload_alexa_style(self, client, mystic_msg, file_path, is_video, title, duration, user_name, vidid=None):
        if not file_path or not os.path.exists(file_path):
            return False

        caption = f"**الـعـنـوان:** {title}\n**طـلـب:** {user_name}"
        chat_id = mystic_msg.chat.id
        
        # البحث عن ملف الغلاف (الصورة)
        thumb_path = None
        if vidid:
            # yt-dlp قد يحفظ الصورة بصيغ مختلفة (webp, jpg, png)
            # نبحث عن أي ملف يبدأ بـ ID وليس فيديو أو صوت
            possible_files = glob.glob(os.path.join(Config.DOWNLOAD_PATH, f"{vidid}*"))
            for f in possible_files:
                if f.endswith((".jpg", ".webp", ".png", ".jpeg")):
                    thumb_path = f
                    break
        
        try:
            if is_video:
                media = InputMediaVideo(
                    media=file_path,
                    thumb=thumb_path, # هنا يتم تمرير الغلاف للفيديو
                    caption=caption,
                    duration=duration,
                    supports_streaming=True
                )
            else:
                media = InputMediaAudio(
                    media=file_path,
                    thumb=thumb_path, # هنا يتم تمرير الغلاف للصوت
                    caption=caption,
                    duration=duration,
                    title=title,
                    performer=user_name
                )
            
            await mystic_msg.edit_media(media=media)
            
        except Exception:
            try:
                await mystic_msg.delete()
                if is_video:
                    await client.send_video(
                        chat_id, 
                        video=file_path, 
                        caption=caption, 
                        duration=duration, 
                        thumb=thumb_path, # محاولة ثانية في الإرسال الجديد
                        supports_streaming=True
                    )
                else:
                    await client.send_audio(
                        chat_id, 
                        audio=file_path, 
                        caption=caption, 
                        duration=duration, 
                        title=title, 
                        performer=user_name, 
                        thumb=thumb_path # محاولة ثانية
                    )
            except Exception as e:
                print(f"Upload Error: {e}")
                return False

        # تنظيف صورة الغلاف بعد الإرسال
        if thumb_path and os.path.exists(thumb_path):
            try: os.remove(thumb_path)
            except: pass
            
        return True

Processor = YTProcessorAPI()
