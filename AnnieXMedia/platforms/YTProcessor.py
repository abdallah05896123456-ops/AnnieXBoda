# تم التطوير بواسطة Certified Coders 2026
# معالج العمليات النووي: نظام المحاولة المزدوجة (Fallback System)
# يحل مشكلة "Sign in to confirm" عبر التبديل التلقائي بين العملاء

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
    DOWNLOAD_PATH = "/dev/shm/AnnieDownloads" if os.path.exists("/dev/shm") else "downloads"
    # استخدام User-Agent عام جداً لتقليل الشكوك
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    MAX_WORKERS = 16

if not os.path.exists(Config.DOWNLOAD_PATH):
    os.makedirs(Config.DOWNLOAD_PATH, exist_ok=True)

class YTProcessorAPI:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)

    def get_cookie_file(self):
        """البحث عن الكوكيز"""
        paths = ["cookies.txt", "AnnieXMedia/assets/cookies.txt", "assets/cookies.txt"]
        for p in paths:
            if os.path.exists(p) and os.path.getsize(p) > 0:
                return p
        return None

    async def get_quality_buttons(self, vidid, stype):
        """جلب الجودات مع نظام المحاولة المزدوجة لتجاوز الحظر"""
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        cookie_file = self.get_cookie_file()
        
        # المحاولة الأولى: إعدادات قوية (ويب + كوكيز + ريموت)
        ydl_opts_1 = {
            "quiet": True,
            "cookiefile": cookie_file,
            "user_agent": Config.USER_AGENT,
            "remote_components": ["ejs:github"],
            "extractor_args": {"youtube": {"player_client": ["web", "ios"]}}
        }

        # المحاولة الثانية: وضع التخفي (أندرويد + بدون كوكيز)
        ydl_opts_2 = {
            "quiet": True,
            "cookiefile": None, # إلغاء الكوكيز عمداً لتجاوز الحظر
            "user_agent": Config.USER_AGENT,
            "extractor_args": {"youtube": {"player_client": ["android"]}}
        }
        
        loop = asyncio.get_running_loop()

        def _fetch(opts):
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(yturl, download=False)
        
        try:
            # المحاولة الأولى
            info = await loop.run_in_executor(self.pool, lambda: _fetch(ydl_opts_1))
        except Exception as e:
            err_str = str(e).lower()
            if "sign in" in err_str or "bot" in err_str:
                LOGGER(__name__).warning("⚠️ كشف البوت! جاري تفعيل وضع التخفي (بدون كوكيز)...")
                try:
                    # المحاولة الثانية (Fallback)
                    info = await loop.run_in_executor(self.pool, lambda: _fetch(ydl_opts_2))
                except Exception as e2:
                    LOGGER(__name__).error(f"❌ فشلت المحاولة الثانية أيضاً: {e2}")
                    return [[InlineKeyboardButton(text="فـشل الـجـلـب (حـظـر)", callback_data="close")]]
            else:
                LOGGER(__name__).error(f"❌ خطأ غير متعلق بالحظر: {e}")
                return [[InlineKeyboardButton(text="خـطـأ فـني", callback_data="close")]]

        formats = info.get("formats", [])
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
        """تحميل مع نظام المحاولة المزدوجة"""
        vid_id = str(int(time.time()))
        ext = "mp4" if is_video else "mp3"
        final_file = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id}.{ext}")
        cookie_file = self.get_cookie_file()
        
        # إعدادات أساسية
        base_opts = {
            "outtmpl": os.path.join(Config.DOWNLOAD_PATH, f"{vid_id}.%(ext)s"),
            "user_agent": Config.USER_AGENT,
            "quiet": True,
            "nocheckcertificate": True,
            "external_downloader": "aria2c",
            "external_downloader_args": ["-x", "16", "-s", "16", "-k", "1M"]
        }
        
        if not is_video:
            base_opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}]

        # المحاولة 1: كوكيز + ويب
        opts_1 = base_opts.copy()
        opts_1.update({
            "format": f"{format_id}+bestaudio/best" if is_video else format_id,
            "cookiefile": cookie_file,
            "remote_components": ["ejs:github"],
            "extractor_args": {"youtube": {"player_client": ["web", "ios"]}}
        })

        # المحاولة 2: بدون كوكيز + أندرويد
        opts_2 = base_opts.copy()
        opts_2.update({
            "format": f"{format_id}+bestaudio/best" if is_video else format_id,
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
        except Exception as e:
            if "Sign in" in str(e) or "bot" in str(e).lower():
                LOGGER(__name__).warning("⚠️ فشل التحميل بالكوكيز، جاري المحاولة بدون كوكيز...")
                try:
                    await loop.run_in_executor(self.pool, lambda: _run(opts_2))
                except Exception as e2:
                    LOGGER(__name__).error(f"❌ فشل التحميل النهائي: {e2}")
            else:
                LOGGER(__name__).error(f"❌ خطأ تحميل: {e}")

        return final_file

    async def send_smart_file(self, client, chat_id, file_path, is_video, title, duration, thumb, user_name):
        if not os.path.exists(file_path):
            LOGGER(__name__).error(f"الملف غير موجود للإرسال: {file_path}")
            return False

        from AnnieXMedia import userbot
        caption = f"الـعـنـوان: {title}\nطـلـب: {user_name}"
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

            if os.path.exists(file_path): os.remove(file_path)
            return True
        except Exception as e:
            LOGGER(__name__).error(f"خطأ الإرسال: {e}")
            return False

Processor = YTProcessorAPI()
