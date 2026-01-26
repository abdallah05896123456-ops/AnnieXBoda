# تم التطوير بواسطة Certified Coders 2026
# معالج الكوكيز الذكي: تدوير عشوائي + حذف التالف تلقائياً + 16 نواة

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
    # متصفح حديث جداً
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    MAX_WORKERS = 16

if not os.path.exists(Config.DOWNLOAD_PATH):
    os.makedirs(Config.DOWNLOAD_PATH, exist_ok=True)

class YTProcessorAPI:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)

    def get_cookie_file(self):
        """نظام تدوير الكوكيز العشوائي"""
        # التأكد من وجود المجلد
        cookie_dir = "cookies"
        if not os.path.exists(cookie_dir):
            os.makedirs(cookie_dir, exist_ok=True)
            
        # البحث عن ملفات txt
        files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
        
        # البحث في مسارات بديلة أيضاً
        if not files:
            alternate_paths = ["AnnieXMedia/assets/cookies.txt", "assets/cookies.txt", "cookies.txt"]
            for p in alternate_paths:
                if os.path.exists(p) and os.path.getsize(p) > 0:
                    return p
            return None

        # اختيار ملف عشوائي لتوزيع الحمل
        selected = random.choice(files)
        return os.path.join(cookie_dir, selected)

    def remove_bad_cookie(self, cookie_path):
        """حذف الكوكيز التالفة لعدم استخدامها مرة أخرى"""
        if cookie_path and os.path.exists(cookie_path) and "cookies" in cookie_path:
            try:
                os.remove(cookie_path)
                LOGGER(__name__).warning(f"🗑️ تم حذف كوكيز تالف: {cookie_path}")
            except:
                pass

    async def get_quality_buttons(self, vidid, stype):
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        cookie_file = self.get_cookie_file()
        
        ydl_opts = {
            "quiet": True,
            "cookiefile": cookie_file,
            "user_agent": Config.USER_AGENT,
            "remote_components": ["ejs:github"],
            "nocheckcertificate": True,
            "extractor_args": {"youtube": {"player_client": ["web", "ios"]}}
        }
        
        loop = asyncio.get_running_loop()
        def _fetch():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(yturl, download=False)
        
        try:
            info = await loop.run_in_executor(self.pool, _fetch)
            formats = info.get("formats", [])
        except Exception as e:
            # إذا كان الخطأ بسبب الحظر، نحذف الكوكيز ونحاول مرة أخرى
            if "Sign in" in str(e) and cookie_file:
                self.remove_bad_cookie(cookie_file)
            LOGGER(__name__).error(f"خطأ الجودات: {e}")
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

    async def download_file(self, url, format_id, is_video, title):
        vid_id = str(int(time.time()))
        ext = "mp4" if is_video else "mp3"
        final_file = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id}.{ext}")
        cookie_file = self.get_cookie_file()
        
        ydl_opts = {
            "format": f"{format_id}+bestaudio/best" if is_video else format_id,
            "outtmpl": os.path.join(Config.DOWNLOAD_PATH, f"{vid_id}.%(ext)s"),
            "cookiefile": cookie_file,
            "user_agent": Config.USER_AGENT,
            "remote_components": ["ejs:github"],
            "quiet": True,
            "nocheckcertificate": True,
            "external_downloader": "aria2c",
            "external_downloader_args": ["-x", "16", "-s", "16", "-k", "1M"]
        }
        
        if not is_video:
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }]

        def _run():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return final_file

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(self.pool, _run)
        except Exception as e:
             if "Sign in" in str(e) and cookie_file:
                self.remove_bad_cookie(cookie_file)
             return None

    async def send_smart_file(self, client, chat_id, file_path, is_video, title, duration, thumb, user_name):
        if not file_path or not os.path.exists(file_path):
            return False

        from AnnieXMedia import userbot
        caption = f"الـعـنـوان: {title}\nطـلـب: {user_name}"
        filesize = os.path.getsize(file_path) / (1024 * 1024)
        
        try:
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

            if os.path.exists(file_path): os.remove(file_path)
            return True
        except Exception:
            return False

Processor = YTProcessorAPI()
