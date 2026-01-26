# تم التطوير بواسطة Certified Coders 2026
# المحرك النووي: كاش ذكي + تخصيص الجودة حسب الرتبة + سرعة قصوى

import asyncio
import os
import time
import random
import yt_dlp
from typing import Union, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
from pyrogram.enums import ChatAction
from pyrogram.types import InlineKeyboardButton

from config import LOGGER_ID
from AnnieXMedia import userbot, LOGGER
from AnnieXMedia.utils.formatters import convert_bytes

class Config:
    DOWNLOAD_PATH = "/dev/shm/AnnieDownloads" if os.path.exists("/dev/shm") else "downloads"
    # User-Agent حديث
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    MAX_WORKERS = 16

if not os.path.exists(Config.DOWNLOAD_PATH):
    os.makedirs(Config.DOWNLOAD_PATH, exist_ok=True)

class YTProcessorAPI:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)

    def get_cookie_file(self):
        """نظام تدوير الكوكيز"""
        paths = ["cookies.txt", "AnnieXMedia/assets/cookies.txt", "assets/cookies.txt", "AnnieXMedia/cookies.txt"]
        if os.path.exists("cookies"):
            for f in os.listdir("cookies"):
                if f.endswith(".txt"): paths.append(os.path.join("cookies", f))
        
        valid = [p for p in paths if os.path.exists(p) and os.path.getsize(p) > 0]
        return random.choice(valid) if valid else None

    async def get_quality_buttons(self, vidid, stype):
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
        
        try:
            info = await loop.run_in_executor(self.pool, _fetch)
            formats = info.get("formats", [])
        except:
            # Fallback to Android if Web fails
            try:
                ydl_opts["extractor_args"] = {"youtube": {"player_client": ["android"]}}
                ydl_opts["cookiefile"] = None
                info = await loop.run_in_executor(self.pool, _fetch)
                formats = info.get("formats", [])
            except:
                return [[InlineKeyboardButton(text="جـودة تـلـقـائـيـة", callback_data=f"song_download audio|bestaudio|{vidid}")]]

        keyboard = []
        if stype == "audio":
            done = []
            for x in formats:
                if x.get("acodec") != "none" and x.get("filesize"):
                    form = "MP3 HQ" if x.get("abr", 0) >= 128 else "Audio"
                    if form not in done:
                        done.append(form)
                        keyboard.append([InlineKeyboardButton(text=f"صـوت {form} | {convert_bytes(x['filesize'])}", callback_data=f"song_download audio|{x['format_id']}|{vidid}")])
        else:
            allowed = ["160", "133", "134", "135", "136", "137", "298", "299", "264", "304", "266"]
            for x in formats:
                if x.get("format_id") in allowed and x.get("filesize"):
                    res = x.get("format_note", "HD")
                    keyboard.append([InlineKeyboardButton(text=f"فـيـديـو {res} | {convert_bytes(x['filesize'])}", callback_data=f"song_download video|{x['format_id']}|{vidid}")])
        
        keyboard.append([InlineKeyboardButton(text="إغـلاق", callback_data="close")])
        return keyboard

    async def download_file(self, url, format_id, is_video, title, vidid=None, is_owner=False):
        """
        التحميل الذكي:
        - is_owner=True: تحميل بأعلى جودة (320kbps للصوت / 4K للفيديو).
        - is_owner=False: تحميل بجودة سريعة (128kbps للصوت / 720p للفيديو).
        """
        vid_id_str = vidid if vidid else str(int(time.time()))
        ext = "mp4" if is_video else "mp3"
        final_file = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.{ext}")
        
        # ⚡⚡ الكاش: لو الملف موجود بنفس الاسم، ابعته فوراً ⚡⚡
        if os.path.exists(final_file) and os.path.getsize(final_file) > 1024:
            return final_file

        cookie_file = self.get_cookie_file()
        
        base_opts = {
            "outtmpl": os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.%(ext)s"),
            "user_agent": Config.USER_AGENT,
            "quiet": True,
            "nocheckcertificate": True,
            "external_downloader": "aria2c",
            "external_downloader_args": ["-x", "16", "-s", "16", "-k", "1M"],
            "writethumbnail": True,
        }
        
        if is_video:
            if is_owner:
                # للمطور: هات أعلى جودة موجودة في اليوتيوب كله
                fmt = f"bestvideo+bestaudio/best"
            else:
                # للمستخدم العادي: أقصى جودة 720p عشان السرعة والنت
                fmt = f"bestvideo[height<=720]+bestaudio/best[height<=720]/best"
        else:
            # للصوت
            if is_owner:
                # للمطور: 320kbps (تاخد وقت شوية في المعالجة)
                fmt = f"{format_id if format_id else 'bestaudio'}/best"
                quality = '320'
            else:
                # للمستخدم العادي: 128kbps (صاروخ في التحميل والمعالجة)
                fmt = f"{format_id if format_id else 'bestaudio'}/best"
                quality = '128' # تقليل الجودة لزيادة السرعة حسب طلبك
                
            base_opts["postprocessors"] = [
                {'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': quality},
                {'key': 'EmbedThumbnail'}, 
                {'key': 'FFmpegMetadata', 'add_metadata': True}
            ]

        # المحاولة 1: ويب
        opts_1 = base_opts.copy()
        opts_1.update({
            "format": fmt,
            "cookiefile": cookie_file,
            "remote_components": ["ejs:github"],
            "extractor_args": {"youtube": {"player_client": ["web"]}}
        })

        # المحاولة 2: أندرويد (Fallback)
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
        except Exception:
            try:
                await loop.run_in_executor(self.pool, lambda: _run(opts_2))
            except:
                return None

        return final_file

    async def send_smart_file(self, client, chat_id, file_path, is_video, title, duration, thumb, user_name):
        if not file_path or not os.path.exists(file_path):
            return False

        from AnnieXMedia import userbot
        caption = f"🏷 **الـعـنـوان:** {title}\n👤 **طـلـب:** {user_name}"
        
        try:
            filesize = os.path.getsize(file_path) / (1024 * 1024)
            if filesize < 50:
                action = ChatAction.UPLOAD_VIDEO if is_video else ChatAction.UPLOAD_AUDIO
                await client.send_chat_action(chat_id, action)
                if is_video:
                    await client.send_video(chat_id, video=file_path, caption=caption, duration=duration, thumb=thumb, supports_streaming=True)
                else:
                    await client.send_audio(chat_id, audio=file_path, caption=caption, duration=duration, title=title, performer=user_name, thumb=thumb)
            else:
                assistant = userbot.one
                if is_video:
                    up = await assistant.send_video(LOGGER_ID, video=file_path, duration=duration, thumb=thumb)
                    await client.send_video(chat_id, video=up.video.file_id, caption=caption, duration=duration, thumb=thumb, supports_streaming=True)
                else:
                    up = await assistant.send_audio(LOGGER_ID, audio=file_path, duration=duration, title=title, performer=user_name, thumb=thumb)
                    await client.send_audio(chat_id, audio=up.audio.file_id, caption=caption, duration=duration, title=title, performer=user_name, thumb=thumb)
                await up.delete()
            return True
        except Exception:
            return False

Processor = YTProcessorAPI()
