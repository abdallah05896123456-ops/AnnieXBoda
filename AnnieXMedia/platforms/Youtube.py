# Authored By Certified Coders © 2025
# Fixed for platforms/Youtube.py
# NUCLEAR EDITION: 16-Core Aria2c Download + Instant Direct Stream + RAM Disk

import asyncio
import os
import re
import logging
from typing import Union, List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
import time
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message, InlineKeyboardButton
from youtubesearchpython.aio import VideosSearch

try:
    from AnnieXMedia.utils.formatters import time_to_seconds, convert_bytes
    from AnnieXMedia import LOGGER
except ImportError:
    logging.basicConfig(level=logging.ERROR)
    def LOGGER(name): return logging.getLogger(name)
    def time_to_seconds(t): return 0
    def convert_bytes(b): return "0 B"

class Config:
    # استخدام الرام ديسك للحصول على سرعة خرافية في المعالجة
    if os.path.exists("/dev/shm"):
        DOWNLOAD_PATH = "/dev/shm/AnnieDownloads"
    else:
        DOWNLOAD_PATH = os.path.abspath("downloads")
    
    COOKIE_PATH = "AnnieXMedia/assets/cookies.txt"
    # استغلال الـ 16 كور بالكامل للعمليات المتوازية
    MAX_WORKERS = 16

if not os.path.exists(Config.DOWNLOAD_PATH):
    os.makedirs(Config.DOWNLOAD_PATH, exist_ok=True)

_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()
YOUTUBE_META_TTL = 3600

def get_cookie_file():
    possible_paths = [
        Config.COOKIE_PATH, "cookies.txt", "AnnieXMedia/cookies.txt",
        "assets/cookies.txt", "platforms/cookies.txt"
    ]
    for path in possible_paths:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    return None

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
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset: break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None if offset in (None,) else text[offset : offset + length]

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        link = link.split("&")[0]

        async with _cache_lock:
            if link in _cache:
                ts, val = _cache[link]
                if time.time() - ts < YOUTUBE_META_TTL:
                    return val[0], val[1]

        try:
            results = VideosSearch(link, limit=1)
            res = await results.next()
            if not res or not res.get("result"):
                raise ValueError("No Result")
            data = res["result"][0]
            
            track_details = {
                "title": data["title"],
                "link": data["link"],
                "vidid": data["id"],
                "duration_min": data["duration"],
                "thumb": data["thumbnails"][0]["url"].split("?")[0],
                "cookiefile": get_cookie_file(),
            }
            async with _cache_lock:
                _cache[link] = (time.time(), (track_details, data["id"]))
            return track_details, data["id"]
        except Exception:
            return {"title": "Unknown", "link": link, "vidid": "error", "duration_min": "0:00", "thumb": ""}, "error"

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

    def _background_download(self, link, final_path, is_video):
        """التحميل الخلفي مع التحويل لـ MP3 باستخدام FFmpeg"""
        try:
            aria2_args = ["-x", "16", "-s", "16", "-j", "16", "-k", "1M"]
            if is_video:
                ydl_opts = {
                    "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]",
                    "outtmpl": final_path,
                    "external_downloader": "aria2c",
                    "external_downloader_args": aria2_args,
                    "cookiefile": get_cookie_file(),
                }
            else:
                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": final_path.replace(".mp3", ""),
                    "cookiefile": get_cookie_file(),
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "320",
                    }],
                }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
        except Exception:
            pass

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> Tuple[Optional[str], bool]:
        
        if videoid: link = self.base + link
        loop = asyncio.get_running_loop()
        is_vid = (video or songvideo)

        try:
            if "v=" in link: vid_id = link.split("v=")[1].split("&")[0]
            else: vid_id = str(int(time.time()))
        except: vid_id = str(int(time.time()))

        ext = "mp4" if is_vid else "mp3"
        ram_path = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id}.{ext}")

        if os.path.exists(ram_path) and os.path.getsize(ram_path) > 1024:
            return ram_path, False

        try:
            cmd = ["yt-dlp", "-g", "--cookies", get_cookie_file() or "", "--remote-components", "ejs:github"]
            cmd.extend(["-f", "best[height<=720]" if is_vid else "bestaudio"])
            cmd.append(link)

            process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await process.communicate()

            if stdout:
                direct_link = stdout.decode().split("\n")[0].strip()
                loop.run_in_executor(self.pool, self._background_download, link, ram_path, is_vid)
                return direct_link, True
        except Exception:
            pass

        def _fallback_download():
            try:
                fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]" if is_vid else "bestaudio/best"
                ydl_opts = {"format": fmt, "outtmpl": ram_path, "cookiefile": get_cookie_file(), "quiet": True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([link])
                return ram_path
            except: return None

        downloaded_file = await loop.run_in_executor(self.pool, _fallback_download)
        return downloaded_file, False

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        ytdl_opts = {"quiet": True, "cookiefile": get_cookie_file(), "remote_components": "ejs:github"}
        with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
            formats_available = []
            try:
                r = ydl.extract_info(link, download=False)
                for format in r.get("formats", []):
                    formats_available.append({
                        "format": format["format"],
                        "filesize": format.get("filesize"),
                        "format_id": format["format_id"],
                        "ext": format["ext"],
                        "yturl": link,
                    })
            except: pass
        return formats_available, link

    async def get_quality_buttons(self, vidid, stype):
        """توليد أزرار الجودات من داخل المحرك بنسق مطول"""
        formats_available, _ = await self.formats(vidid, True)
        keyboard = []
        if stype == "audio":
            done = []
            for x in formats_available:
                if "audio" in x.get("format"):
                    if x.get("filesize") is None: continue
                    form = x.get("format_note", "Audio").title()
                    if form not in done: 
                        done.append(form)
                        keyboard.append([InlineKeyboardButton(text=f"صـوت {form} الـحـجـم {convert_bytes(x.get('filesize'))}", callback_data=f"song_download {stype}|{x.get('format_id')}|{vidid}")])
        else:
            allowed_ids = [160, 133, 134, 135, 136, 137, 298, 299, 264, 304, 266]
            for x in formats_available:
                if x.get("filesize") is None or int(x.get("format_id")) not in allowed_ids: continue
                res = x.get("format").split("-")[1] if "-" in x.get("format") else "Video"
                keyboard.append([InlineKeyboardButton(text=f"فـيـديـو {res} الـحـجـم {convert_bytes(x.get('filesize'))}", callback_data=f"song_download {stype}|{x.get('format_id')}|{vidid}")])
        keyboard.append([InlineKeyboardButton(text="رجـوع", callback_data=f"song_back {stype}|{vidid}")])
        keyboard.append([InlineKeyboardButton(text="إغـلاق", callback_data="close")])
        return keyboard

    async def send_nuclear_file(self, client, chat_id, file_path, is_direct, is_video, title, duration, thumb, user_name):
        """دالة الرفع والتنظيف التلقائي للمحرك النووي"""
        from pyrogram import enums
        caption = f"طـلـب بـواسـطـة {user_name}"
        try:
            if is_video:
                await client.send_chat_action(chat_id, enums.ChatAction.UPLOAD_VIDEO)
                await client.send_video(chat_id=chat_id, video=file_path, caption=caption, duration=duration, thumb=thumb, supports_streaming=True)
            else:
                await client.send_chat_action(chat_id, enums.ChatAction.UPLOAD_AUDIO)
                await client.send_audio(chat_id=chat_id, audio=file_path, caption=caption, duration=duration, title=title, performer="الـمـحـرك الـنـووي", thumb=thumb)
            if not is_direct and os.path.exists(file_path): os.remove(file_path)
            if thumb and os.path.exists(thumb): os.remove(thumb)
            return True
        except: return False

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        try:
            a = VideosSearch(link, limit=5)
            res = await a.next()
            if not res or not res.get("result"): return "Error", "0", "", "error"
            r = res["result"][query_type] if query_type < len(res["result"]) else res["result"][0]
            return r["title"], r["duration"], r["thumbnails"][0]["url"].split("?")[0], r["id"]
        except: return "Error", "0", "", "error"

YouTube = YouTubeAPI()
