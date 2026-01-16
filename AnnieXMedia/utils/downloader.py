# Authored By Certified Coders © 2025
# ULTIMATE TITAN EDITION: AnnieX Class Structure + Aria2c Speed + Cache Cleaner + Fly.io Fix

import asyncio
import os
import re
import json
import requests
import shutil
import time
from typing import Union, Tuple, Optional, Dict, List

from yt_dlp import YoutubeDL
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
# ✅ استيراد المكتبة بالتحديث الجديد
from youtubesearchpython.__future__ import VideosSearch, Playlist

# === AnnieX Imports ===
from AnnieXMedia.utils.database import is_on_off
from AnnieXMedia.utils.formatters import time_to_seconds
from AnnieXMedia.utils.errors import capture_internal_err

# === Constants & Cookie Handling ===
COOKIE_FILE_NAME = "cookies.txt"
DOWNLOAD_DIR = "downloads"

# إعدادات Aria2c الصاروخية (موحدة لكل الدوال)
ARIA_OPTS = {
    'external_downloader': 'aria2c',
    'external_downloader_args': [
        '-x', '16',   # 16 خط اتصال
        '-s', '16',   # تقسيم 16 جزء
        '-j', '16',   # تحميل متوازي
        '-k', '1M',   # حجم القطعة
        '--file-allocation=none',
    ]
}

# تأكد من وجود مجلد التحميل
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# --- 1. Auto Cache Cleaner ---
def _clean_stale_files():
    """تنظيف الملفات القديمة لتوفير المساحة على Fly.io"""
    now = time.time()
    ttl = 900 
    try:
        for filename in os.listdir(DOWNLOAD_DIR):
            file_path = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.isfile(file_path):
                if os.stat(file_path).st_mtime < now - ttl:
                    os.remove(file_path)
    except Exception:
        pass

# --- 2. Cookie Loader (FIXED) ---
def _download_cookies_from_secret():
    """تحميل الكوكيز بشكل آمن لا يسبب كراش"""
    cookie_url = os.getenv("COOKIE_URL")
    if not cookie_url:
        return

    # لو الملف موجود وفيه بيانات، متضيعش وقت في التحميل
    if os.path.exists(COOKIE_FILE_NAME) and os.path.getsize(COOKIE_FILE_NAME) > 0:
        return

    try:
        # ✅ أهم تعديل: Catch Exception
        # لو فشل التحميل لأي سبب، البوت مش هيموت، هيكمل عادي
        response = requests.get(cookie_url, timeout=10)
        if response.status_code == 200:
            if not response.text.startswith("# Netscape") and not response.text.startswith("# HTTP"):
                print("WARNING: Cookie URL returned HTML! Check your link.")
            
            with open(COOKIE_FILE_NAME, "w") as f:
                f.write(response.text)
            print("Cookies loaded successfully.")
    except Exception as e:
        # مجرد طباعة الخطأ والاستمرار
        print(f"⚠️ Error downloading cookies (Ignored): {e}")

# استدعاء الدوال عند التشغيل
_download_cookies_from_secret()
_clean_stale_files()

def cookiefile():
    if os.path.exists(COOKIE_FILE_NAME) and os.path.getsize(COOKIE_FILE_NAME) > 0:
        return COOKIE_FILE_NAME
    return None

# === Alexa Helper ===
async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")

# === Main Class ===
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="
        _clean_stale_files()

    @capture_internal_err
    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    @capture_internal_err
    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
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

    @capture_internal_err
    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        data = await results.next()
        if not data.get("result"):
             return "Unknown", 0, 0, "", ""
             
        for result in data["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    @capture_internal_err
    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    @capture_internal_err
    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    @capture_internal_err
    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    @capture_internal_err
    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        cookies = cookiefile()
        cmd_args = ["yt-dlp", "-g", "-f", "best[height<=?720][width<=?1280]", f"{link}"]
        
        if cookies:
            cmd_args.insert(1, cookies)
            cmd_args.insert(1, "--cookies")

        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (1, stdout.decode().split("\n")[0]) if stdout else (0, stderr.decode())

    @capture_internal_err
    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        
        cmd = (
            f"yt-dlp -i --compat-options no-youtube-unavailable-videos "
            f"--get-id --flat-playlist --playlist-end {limit} --skip-download '{link}' "
            f"2>/dev/null"
        )
        if cookiefile():
             cmd = f"yt-dlp --cookies {cookiefile()} -i --compat-options no-youtube-unavailable-videos --get-id --flat-playlist --playlist-end {limit} --skip-download '{link}' 2>/dev/null"

        playlist = await shell_cmd(cmd)
        try:
            result = [key for key in playlist.split("\n") if key]
        except Exception:
            result = []
        return result

    @capture_internal_err
    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        data = await results.next()
        if not data.get("result"):
             return {}, None
             
        for result in data["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    @capture_internal_err
    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        ytdl_opts = {"quiet": True}
        if cookiefile():
            ytdl_opts["cookiefile"] = cookiefile()

        ydl = YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except Exception:
                    continue
                if "dash" not in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except Exception:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        }
                    )
        return formats_available, link

    @capture_internal_err
    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    # 🔥🔥🔥 الدالة المدمجة (قلب الدمج + Aria2c) 🔥🔥🔥
    @capture_internal_err
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
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None], str]:
        
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()

        # دالة تحميل الصوت الافتراضية
        def audio_dl():
            ydl_optssx = {
                "format": "bestaudio[ext=m4a]/bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                # ✅ Aria2c Turbo
                **ARIA_OPTS,
            }
            if cookiefile():
                ydl_optssx["cookiefile"] = cookiefile()

            with YoutubeDL(ydl_optssx) as x:
                info = x.extract_info(link, False)
                xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(xyz):
                    return xyz
                x.download([link])
                return xyz

        # دالة تحميل الفيديو الافتراضية
        def video_dl():
            ydl_optssx = {
                "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                # ✅ Aria2c Turbo
                **ARIA_OPTS,
            }
            if cookiefile():
                ydl_optssx["cookiefile"] = cookiefile()

            with YoutubeDL(ydl_optssx) as x:
                info = x.extract_info(link, False)
                xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(xyz):
                    return xyz
                x.download([link])
                return xyz

        # --- دوال اليكسا الخاصة ---
        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                # ✅ Aria2c Turbo
                **ARIA_OPTS,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            if cookiefile():
                ydl_optssx["cookiefile"] = cookiefile()
            
            x = YoutubeDL(ydl_optssx)
            x.download([link])

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                # ✅ Aria2c Turbo
                **ARIA_OPTS,
                "merge_output_format": "mp4",
            }
            if cookiefile():
                ydl_optssx["cookiefile"] = cookiefile()
            
            x = YoutubeDL(ydl_optssx)
            x.download([link])

        # === Logic Selection ===
        if songvideo:
            await loop.run_in_executor(None, song_video_dl)
            fpath = f"downloads/{title}.mp4"
            return fpath
        elif songaudio:
            await loop.run_in_executor(None, song_audio_dl)
            fpath = f"downloads/{title}.mp3"
            return fpath
        
        elif video:
            if await is_on_off(1): # لو المود Direct
                direct = True
                downloaded_file = await loop.run_in_executor(None, video_dl)
            else:
                cookies = cookiefile()
                cmd_args = ["yt-dlp", "-g", "-f", "best[height<=?720][width<=?1280]", f"{link}"]
                if cookies:
                    cmd_args.insert(1, cookies)
                    cmd_args.insert(1, "--cookies")

                proc = await asyncio.create_subprocess_exec(
                    *cmd_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    downloaded_file = stdout.decode().split("\n")[0]
                    direct = None
                else:
                    return None, None
        
        else:
            direct = True
            downloaded_file = await loop.run_in_executor(None, audio_dl)
        
        return downloaded_file, direct
