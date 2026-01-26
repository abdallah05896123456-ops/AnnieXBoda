# Authored By Certified Coders © 2026
# THE TITAN PROCESSOR: Advanced Anti-Bot Bypass + JS Challenge Solver
# INTEGRATED: 16-Core Aria2c + Invisible Assistant + Remote EJS Component

import asyncio
import os
import time
import yt_dlp
from typing import Union, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
from pyrogram.enums import ChatAction
from pyrogram.types import InlineKeyboardButton

from config import LOGGER_ID
from AnnieXMedia import userbot, LOGGER
from AnnieXMedia.utils.formatters import convert_bytes

class Config:
    # الرام ديسك (50GB) للسرعة اللحظية
    DOWNLOAD_PATH = "/dev/shm/AnnieDownloads" if os.path.exists("/dev/shm") else "downloads"
    # متصفح حديث جداً (Chrome 121) لتمويه يوتيوب
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    MAX_WORKERS = 16

if not os.path.exists(Config.DOWNLOAD_PATH):
    os.makedirs(Config.DOWNLOAD_PATH, exist_ok=True)

class YTProcessorAPI:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)

    def get_cookie_file(self):
        """البحث الذكي والقوي عن الكوكيز لفك الحظر"""
        if os.path.exists("cookies"):
            for f in os.listdir("cookies"):
                if f.endswith(".txt"):
                    return os.path.join("cookies", f)
        # مسارات بديلة لو مجلد cookies فاضي
        paths = ["AnnieXMedia/assets/cookies.txt", "assets/cookies.txt", "cookies.txt"]
        for p in paths:
            if os.path.exists(p) and os.path.getsize(p) > 0:
                return p
        return None

    async def get_quality_buttons(self, vidid, stype):
        """حل مشكلة Signature solving failed وجلب كل الجودات"""
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        
        # إعدادات فك التشفير النووية
        ydl_opts = {
            "quiet": True,
            "cookiefile": self.get_cookie_file(),
            "user_agent": Config.USER_AGENT,
            "nocheckcertificate": True,
            "geo_bypass": True,
            # الحل السحري لمشكلة "confirm you're not a bot"
            "remote_components": ["ejs:github"], 
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}}
        }
        
        loop = asyncio.get_running_loop()
        def _fetch():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(yturl, download=False)
        
        try:
            info = await loop.run_in_executor(self.pool, _fetch)
            formats = info.get("formats", [])
        except Exception as e:
            LOGGER(__name__).error(f"Challenge Solver Failed: {e}")
            return [[InlineKeyboardButton(text="فـشل فـك الـتـشفـير", callback_data="close")]]

        keyboard = []
        if stype == "audio":
            done = []
            for x in formats:
                if "audio" in x.get("format", "").lower() and x.get("filesize"):
                    form = "MP3 HQ" if x.get("abr", 0) >= 128 else "Audio"
                    if form not in done:
                        done.append(form)
                        keyboard.append([InlineKeyboardButton(text=f"صـوت {form} | {convert_bytes(x['filesize'])}", callback_data=f"song_download audio|{x['format_id']}|{vidid}")])
        else:
            # جودات الفيديو المعتمدة في تليجرام
            allowed = ["160", "133", "134", "135", "136", "137", "298", "299", "264", "304", "266"]
            for x in formats:
                if x.get("format_id") in allowed and x.get("filesize"):
                    res = x.get("format_note", "HD")
                    keyboard.append([InlineKeyboardButton(text=f"فـيـديـو {res} | {convert_bytes(x['filesize'])}", callback_data=f"song_download video|{x['format_id']}|{vidid}")])
        
        keyboard.append([InlineKeyboardButton(text="إغـلاق", callback_data="close")])
        return keyboard

    async def download_file(self, url, format_id, is_video, title):
        """التحميل النووي بـ 16 اتصال Aria2c مع تخطي الحظر"""
        vid_id = str(int(time.time()))
        ext = "mp4" if is_video else "mp3"
        file_path = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id}.{ext}")
        
        ydl_opts = {
            "format": f"{format_id}+bestaudio/best" if is_video else format_id,
            "outtmpl": file_path.replace(".mp3", ""),
            "cookiefile": self.get_cookie_file(),
            "user_agent": Config.USER_AGENT,
            "remote_components": ["ejs:github"], # لفك تشفير الرابط قبل التحميل
            "nocheckcertificate": True,
            "quiet": True,
            "external_downloader": "aria2c",
            "external_downloader_args": ["-x", "16", "-s", "16", "-k", "1M", "--file-allocation=none"]
        }
        
        if not is_video:
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }]

        def _run():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
            return file_path

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.pool, _run)

    async def send_nuclear_file(self, client, chat_id, file_path, is_video, title, duration, thumb, user_name):
        """تكنيك أليكسا الخفي: إرسال ملفات حتى 2 جيجا بدون ظهور المساعد"""
        caption = f"**الـعـنـوان:** {title}\n**طـلـب:** {user_name}"
        filesize = os.path.getsize(file_path) / (1024 * 1024)
        
        try:
            # 1. إرسال مباشر للبوت (للملفات < 50MB)
            if filesize < 50:
                action = ChatAction.UPLOAD_VIDEO if is_video else ChatAction.UPLOAD_AUDIO
                await client.send_chat_action(chat_id, action)
                if is_video:
                    await client.send_video(chat_id, video=file_path, caption=caption, duration=duration, thumb=thumb, supports_streaming=True)
                else:
                    await client.send_audio(chat_id, audio=file_path, caption=caption, duration=duration, title=title, performer="المحرك النووي", thumb=thumb)
            
            # 2. التكنيك الخفي (للملفات الضخمة)
            else:
                assistant = userbot.one # استخدام أول مساعد
                if is_video:
                    up = await assistant.send_video(LOGGER_ID, video=file_path, duration=duration, thumb=thumb)
                    await client.send_video(chat_id, video=up.video.file_id, caption=caption, duration=duration, thumb=thumb, supports_streaming=True)
                else:
                    up = await assistant.send_audio(LOGGER_ID, audio=file_path, duration=duration, title=title, thumb=thumb)
                    await client.send_audio(chat_id, audio=up.audio.file_id, caption=caption, duration=duration, title=title, thumb=thumb)
                await up.delete() # مسح من اللوج لتوفير المساحة

            if os.path.exists(file_path): os.remove(file_path)
            return True
        except Exception as e:
            LOGGER(__name__).error(f"Nuclear Send Error: {e}")
            return False

Processor = YTProcessorAPI()
