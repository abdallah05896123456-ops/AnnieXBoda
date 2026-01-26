# Authored By Certified Coders © 2026
# THE INFINITY EDITION: Anti-Bot Bypass + Alexa Secret Technique
# FULL CODE: 16-Core Aria2c + Invisible Assistant + RAM Disk Cache + Slider + Playlist

import asyncio
import os
import re
import logging
import time
import json
from typing import Union, List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor

import yt_dlp
from pyrogram.enums import MessageEntityType, ChatAction
from pyrogram.types import Message, InlineKeyboardButton
from youtubesearchpython.aio import VideosSearch

# استيراد الأدوات المساعدة من قلب السورس
try:
    from AnnieXMedia.utils.formatters import time_to_seconds, convert_bytes
    from AnnieXMedia import LOGGER
except ImportError:
    logging.basicConfig(level=logging.ERROR)
    def LOGGER(name): return logging.getLogger(name)
    def time_to_seconds(t): return 0
    def convert_bytes(b): return "0 B"

class Config:
    # تهيئة المسارات في الرام ديسك 50 جيجا للسرعة الخارقة
    if os.path.exists("/dev/shm"):
        DOWNLOAD_PATH = "/dev/shm/AnnieDownloads"
    else:
        DOWNLOAD_PATH = os.path.abspath("downloads")
    
    # رأس المتصفح (User-Agent) حديث جداً لمحاكاة إنسان حقيقي ومنع حظر يوتيوب
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    MAX_WORKERS = 16

if not os.path.exists(Config.DOWNLOAD_PATH):
    os.makedirs(Config.DOWNLOAD_PATH, exist_ok=True)

# نظام كاش البيانات الوصفية لتقليل طلبات يوتيوب
_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()

def get_cookie_file():
    """البحث الذكي عن الكوكيز لفك حظر يوتيوب فوراً"""
    if os.path.exists("cookies"):
        for f in os.listdir("cookies"):
            if f.endswith(".txt"): return os.path.join("cookies", f)
    
    paths = [
        "AnnieXMedia/assets/cookies.txt", "cookies.txt", 
        "assets/cookies.txt", "platforms/cookies.txt"
    ]
    for p in paths:
        if os.path.exists(p) and os.path.getsize(p) > 0: return p
    return None

async def shell_cmd(cmd):
    """تنفيذ أوامر النظام بسرعة عالية لمعالجة البلاي ليست"""
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, _ = await proc.communicate()
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://www.youtube.com/playlist?list="
        self.pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message: messages.append(message_1.reply_to_message)
        text, offset, length = "", None, None
        for message in messages:
            if offset: break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
        return None if offset is None else text[offset : offset + length]

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        link = link.split("&")[0]
        async with _cache_lock:
            if link in _cache:
                ts, val = _cache[link]
                if time.time() - ts < 3600: return val[0], val[1]
        try:
            results = VideosSearch(link, limit=1)
            res = await results.next()
            data = res["result"][0]
            track_details = {
                "title": data["title"], "link": data["link"],
                "vidid": data["id"], "duration_min": data["duration"],
                "thumb": data["thumbnails"][0]["url"].split("?")[0],
                "cookiefile": get_cookie_file(),
            }
            async with _cache_lock:
                _cache[link] = (time.time(), (track_details, data["id"]))
            return track_details, data["id"]
        except:
            return {"title": "Unknown", "vidid": "error"}, "error"

    async def details(self, link: str, videoid: Union[bool, str] = None):
        d, i = await self.track(link, videoid)
        if i == "error": return None
        return d["title"], d["duration_min"], time_to_seconds(d["duration_min"]), d["thumb"], i

    async def title(self, link: str, videoid: Union[bool, str] = None):
        d, _ = await self.track(link, videoid)
        return d.get("title")

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        d, _ = await self.track(link, videoid)
        return d.get("duration_min")

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        d, _ = await self.track(link, videoid)
        return d.get("thumb")

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        """حل مشكلة البلاي ليست مع الكوكيز لمنع الحظر"""
        if videoid: link = self.listbase + link
        cookie = get_cookie_file()
        cookie_cmd = f"--cookies {cookie}" if cookie else ""
        cmd = f"yt-dlp -i --get-id --flat-playlist --playlist-end {limit} {cookie_cmd} --user-agent '{Config.USER_AGENT}' --skip-download '{link}' 2>/dev/null"
        playlist = await shell_cmd(cmd)
        try: result = [key for key in playlist.split("\n") if key]
        except: result = []
        return result

    def _background_download(self, link, final_path, is_video):
        """التحميل الخلفي بـ 16 اتصال Aria2c مع تمويه كامل"""
        try:
            aria2_args = ["-x", "16", "-s", "16", "-j", "16", "-k", "1M", "--file-allocation=none"]
            fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]" if is_video else "bestaudio[ext=m4a]/bestaudio"
            ydl_opts = {
                "format": fmt, "outtmpl": final_path, "cookiefile": get_cookie_file(),
                "user_agent": Config.USER_AGENT, "quiet": True, "nocheckcertificate": True,
                "external_downloader": "aria2c", "external_downloader_args": aria2_args,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([link])
        except: pass

    async def download(self, link, mystic, video=None, videoid=None, songaudio=None, songvideo=None, format_id=None, title=None):
        """المحرك النووي: يعالج البث المباشر (المكالمة) والتنزيل (الدردشة) بشكل منفصل"""
        if not videoid: _, vid_id = await self.track(link)
        else: vid_id = videoid

        loop = asyncio.get_running_loop()
        is_vid = (video or songvideo)
        ext = "mp4" if is_vid else "mp3"
        ram_path = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id}.{ext}")

        # كاش أليكسا: لو الملف موجود نرجعه فوراً
        if os.path.exists(ram_path) and os.path.getsize(ram_path) > 1024:
            return ram_path, False

        # --- ممر البث الصوتي المباشر (Direct Link) للمكالمات ---
        if not is_vid and not songaudio:
            try:
                cookie = get_cookie_file()
                # إضافة كل رؤوس التمويه لمنع رسالة "Confirm you're not a bot"
                cmd = ["yt-dlp", "-g", "--user-agent", Config.USER_AGENT, "--no-check-certificates", "--geo-bypass"]
                if cookie: cmd.extend(["--cookies", cookie])
                cmd.extend(["-f", "bestaudio", link])
                
                process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await process.communicate()
                
                if stdout:
                    direct_link = stdout.decode().split("\n")[0].strip()
                    # تحميل خلفي للكاش دون تعطيل البث
                    loop.run_in_executor(self.pool, self._background_download, link, ram_path, False)
                    return direct_link, True
                else:
                    LOGGER(__name__).error(f"YT-DLP Error Bypass: {stderr.decode()}")
            except: pass

        # --- ممر التنزيل الفعلي لملفات الصوت والفيديو ---
        def _execute_dl():
            try:
                fmt = f"{format_id}+bestaudio/best" if format_id else "bestvideo[height<=720]+bestaudio/best"
                ydl_opts = {
                    "format": fmt, "outtmpl": ram_path.replace(".mp3", ""), "quiet": True,
                    "cookiefile": get_cookie_file(), "user_agent": Config.USER_AGENT, "nocheckcertificate": True
                }
                if songaudio:
                    ydl_opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}]
                with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([link])
                return ram_path
            except: return None

        res = await loop.run_in_executor(self.pool, _execute_dl)
        return res, False

    async def send_nuclear_file(self, client, chat_id, file_path, is_direct, is_video, title, duration, thumb, user_name):
        """دالة الرفع النووي: المساعد يرفع في اللوج والبوت يرسل للمستخدم (خفي)"""
        from AnnieXMedia import userbot, config
        caption = f"**الـعـنـوان:** {title}\n**طـلـب:** {user_name}"
        
        try:
            if is_direct:
                if is_video: await client.send_video(chat_id, video=file_path, caption=caption, duration=duration, thumb=thumb, supports_streaming=True)
                else: await client.send_audio(chat_id, audio=file_path, caption=caption, duration=duration, title=title, performer="المحرك النووي", thumb=thumb)
                return True

            filesize = os.path.getsize(file_path) / (1024 * 1024)

            if filesize < 50:
                if is_video: await client.send_video(chat_id, video=file_path, caption=caption, duration=duration, thumb=thumb, supports_streaming=True)
                else: await client.send_audio(chat_id, audio=file_path, caption=caption, duration=duration, title=title, performer="المحرك النووي", thumb=thumb)
            else:
                assistant = userbot.one
                if is_video:
                    up = await assistant.send_video(config.LOGGER_ID, video=file_path, duration=duration, thumb=thumb)
                    await client.send_video(chat_id, video=up.video.file_id, caption=caption, duration=duration, thumb=thumb, supports_streaming=True)
                else:
                    up = await assistant.send_audio(config.LOGGER_ID, audio=file_path, duration=duration, title=title, thumb=thumb)
                    await client.send_audio(chat_id, audio=up.audio.file_id, caption=caption, duration=duration, title=title, thumb=thumb)
                await up.delete()

            if os.path.exists(file_path) and filesize > 150: os.remove(file_path)
            return True
        except Exception as e:
            LOGGER(__name__).error(f"Nuclear Secret Send Error: {e}")
            return False

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        """جلب الجودات مع تجاوز حظر يوتيوب"""
        if videoid: link = self.base + link
        ydl_opts = {"quiet": True, "cookiefile": get_cookie_file(), "user_agent": Config.USER_AGENT, "nocheckcertificate": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            formats_available = []
            try:
                r = ydl.extract_info(link, download=False)
                for f in r.get("formats", []):
                    formats_available.append({"format": f["format"], "filesize": f.get("filesize"), "format_id": f["format_id"], "ext": f["ext"], "yturl": link})
            except: pass
        return formats_available, link

    async def get_quality_buttons(self, vidid, stype):
        """توليد أزرار الجودات بنسق أليكسا المطول"""
        formats_available, _ = await self.formats(vidid, True)
        keyboard = []
        if stype == "audio":
            done = []
            for x in formats_available:
                if "audio" in x.get("format") and x.get("filesize"):
                    form = "MP3 HQ" if "320" in x.get("format") else "Audio"
                    if form not in done: 
                        done.append(form)
                        keyboard.append([InlineKeyboardButton(text=f"صـوت {form} | {convert_bytes(x['filesize'])}", callback_data=f"song_download audio|{x['format_id']}|{vidid}")])
        else:
            allowed = ["160", "133", "134", "135", "136", "137", "298", "299", "264", "304", "266"]
            for x in formats_available:
                if x.get("format_id") in allowed and x.get("filesize"):
                    keyboard.append([InlineKeyboardButton(text=f"فـيـديـو {x.get('format_note', 'HD')} | {convert_bytes(x['filesize'])}", callback_data=f"song_download video|{x['format_id']}|{vidid}")])
        keyboard.append([InlineKeyboardButton(text="إغـلاق", callback_data="close")])
        return keyboard

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        """نظام البحث المتقدم (Slider) المعتمد في أليكسا"""
        if videoid: link = self.base + link
        try:
            a = VideosSearch(link, limit=10)
            res = await a.next()
            if not res or not res.get("result"): return "Error", "0", "", "error"
            r = res["result"][query_type] if query_type < len(res["result"]) else res["result"][0]
            return r["title"], r["duration"], r["thumbnails"][0]["url"].split("?")[0], r["id"]
        except: return "Error", "0", "", "error"

YouTube = YouTubeAPI()
