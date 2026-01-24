# Authored By Certified Coders © 2025
# Fixed for platforms/Youtube.py location
# Solved "Requested format is not available" error permanently.

import asyncio
import os
import re
import logging
import traceback
from typing import Union, List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
import time

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.aio import VideosSearch

# --- محاولة استيراد الإعدادات (تجاهل الأخطاء لو المسارات مختلفة) ---
try:
    from AnnieXMedia.utils.formatters import time_to_seconds
    from AnnieXMedia import LOGGER
except ImportError:
    logging.basicConfig(level=logging.ERROR)
    def LOGGER(name): return logging.getLogger(name)
    def time_to_seconds(t): return 0

# إخفاء إزعاج المكتبات
logging.getLogger("yt_dlp").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

# --- إعدادات النظام ---
class Config:
    DOWNLOAD_PATH = "downloads"
    # مسارات الكوكيز المحتملة لضمان قراءتها
    COOKIE_PATH = "AnnieXMedia/assets/cookies.txt"
    # عدد الـ Threads (تم رفعه لـ 16 لاستغلال قوة السيرفر)
    MAX_WORKERS = 16 

if not os.path.exists(Config.DOWNLOAD_PATH):
    os.makedirs(Config.DOWNLOAD_PATH)

# --- الكاش (للذاكرة) ---
_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()
YOUTUBE_META_TTL = 3600

# --- دوال المساعدة ---

def get_cookie_file():
    """البحث عن الكوكيز في كل مكان محتمل"""
    possible_paths = [
        Config.COOKIE_PATH,
        "cookies.txt",
        "AnnieXMedia/cookies.txt",
        "assets/cookies.txt",
        "platforms/cookies.txt"
    ]
    for path in possible_paths:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    return None

# --- الكلاس الرئيسي ---

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://www.youtube.com/playlist?list="
        self.pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)
        # التأكد من وجود Aria2
        self.has_aria2 = os.system("which aria2c > /dev/null 2>&1") == 0

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

    # -----------------------------------------------------------------
    # 📥 منطقة التحميل (تم الإصلاح هنا)
    # -----------------------------------------------------------------
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
        
        if videoid: 
            link = self.base + link
        
        # 1. منع الروابط المضروبة
        if "youtube.com/0" in link or link.endswith("="):
            return None, False

        loop = asyncio.get_running_loop()

        # 2. استخراج ID نظيف
        try:
            if "v=" in link: vid_id = link.split("v=")[1].split("&")[0]
            elif "youtu.be/" in link: vid_id = link.split("youtu.be/")[1].split("?")[0]
            else: vid_id = str(int(time.time()))
        except:
             vid_id = str(int(time.time()))

        # 3. إعداد الخيارات (Fixing Format Error)
        # بدلاً من إجبار m4a، نطلب الأفضل ويوتيوب يبعت اللي عنده
        fmt = "bestvideo+bestaudio/best" if video else "bestaudio/best"
        
        ydl_opts = {
            # استخدام %(ext)s عشان نسمح بأي صيغة (webm/m4a/opus)
            "outtmpl": f"{Config.DOWNLOAD_PATH}/{vid_id}.%(ext)s",
            "cookiefile": get_cookie_file(),
            "geo_bypass": True,
            "nocheckcertificate": True,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "overwrites": True,
            "format": fmt, # تم التعديل هنا
            "extractor_args": {
                'youtube': {
                    'skip': ['dash', 'hls'],
                    # iOS هو الأفضل حالياً لتفادي المشاكل
                    'player_client': ['ios', 'android', 'web'], 
                }
            }
        }

        # تسريع التحميل بـ Aria2
        if self.has_aria2:
            ydl_opts["external_downloader"] = "aria2c"
            ydl_opts["external_downloader_args"] = ["-x", "16", "-s", "16", "-k", "1M"]

        def _run_download():
            # البحث عن الملف لو كان موجود أصلاً بأي صيغة
            possible_exts = ["m4a", "mp4", "webm", "opus", "mp3", "mkv"]
            for ext in possible_exts:
                p = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id}.{ext}")
                if os.path.exists(p):
                    return p

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([link])
            except Exception as e:
                LOGGER(__name__).error(f"DL Error: {e}")
                return None
            
            # البحث عن الملف الجديد بعد التحميل (لأننا مش عارفين الصيغة مسبقاً)
            for ext in possible_exts:
                final_path = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id}.{ext}")
                if os.path.exists(final_path):
                    return final_path
            return None

        downloaded_file = await loop.run_in_executor(self.pool, _run_download)
        
        if downloaded_file:
            return downloaded_file, True
        return None, False

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid: link = self.listbase + link
        if "&" in link: link = link.split("&")[0]
        cmd = (
            f"yt-dlp -i --compat-options no-youtube-unavailable-videos "
            f"--get-id --flat-playlist --playlist-end {limit} --skip-download '{link}' "
            f"2>/dev/null"
        )
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await proc.communicate()
        try: result = [key for key in out.decode().split("\n") if key]
        except: result = []
        return result

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        ytdl_opts = {"quiet": True, "cookiefile": get_cookie_file()}
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
