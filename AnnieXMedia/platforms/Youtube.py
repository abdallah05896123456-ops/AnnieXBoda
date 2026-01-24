# Authored By Certified Coders © 2026
# TITANIUM GOD MODE: ULTIMATE LIGHT SPEED ⚡
# SERVER SPECS: 50GB RAM | 2.5Gbps UPLINK
# ENGINE: HYPER-THREADED YT-DLP + RAM DISK + ARIA2 (30MB CHUNKS)

import asyncio
import logging
import os
import re
import shutil
import time
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple, Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.aio import Playlist, VideosSearch

# --- 1. استيراد الأدوات المساعدة ---
try:
    from AnnieXMedia.utils.cookie_handler import COOKIE_PATH
except ImportError:
    COOKIE_PATH = None

try:
    from AnnieXMedia.utils.formatters import time_to_seconds
except ImportError:
    def time_to_seconds(x): return 0

try:
    from AnnieXMedia.utils.database import is_on_off
except ImportError:
    async def is_on_off(x): return True

# --- 2. تفعيل نظام الرامات (RAM DISK I/O) ---
try:
    from AnnieXMedia.core.dir import DOWNLOAD_DIR
except ImportError:
    # Fallback
    DOWNLOAD_DIR = os.path.abspath(os.path.join(os.getcwd(), "downloads"))
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- 3. إعدادات اللوج والمعالجة ---
logging.getLogger("yt_dlp").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
LOG = logging.getLogger("Titan_50GB_RAM")

# 64 Thread لاستغلال قوة المعالج بالكامل
POOL = ThreadPoolExecutor(max_workers=64)

# --- 4. إعدادات Aria2c (BEAST MODE - 30MB chunks) ---
HAS_ARIA2 = shutil.which("aria2c") is not None
ARIA2_ARGS = [
    "-c", 
    "-x", "16",           # 16 خط اتصال متوازي
    "-s", "16",           # تقسيم السيرفر لـ 16 جزء
    "-j", "32",           # 32 مهمة في نفس الوقت
    "-k", "30M",          # ⚡ طلبك: القطعة الواحدة 30 ميجا (للرامات العالية)
    "--min-split-size=30M", # منع تقسيم الملفات الصغيرة (توفير وقت)
    "--file-allocation=none", 
    "--quiet=true",
    "--connect-timeout=5",
    "--max-tries=5",      # زودنا المحاولات عشان الاستقرار
]

# --- 5. نظام الكاش ---
_meta_cache: Dict[str, Tuple[float, Dict]] = {}
_meta_lock = asyncio.Lock()
YOUTUBE_ID_RE = re.compile(r"(?:v=|\/)([A-Za-z0-9_-]{11})")

# --- 6. دوال مساعدة ---

def get_cookie_path() -> Optional[str]:
    if os.path.exists("cookies.txt") and os.path.getsize("cookies.txt") > 0:
        return "cookies.txt"
    paths = [
        os.path.join(os.getcwd(), "AnnieXMedia", "assets", "cookies.txt"),
        str(COOKIE_PATH) if COOKIE_PATH else ""
    ]
    for p in paths:
        if p and os.path.exists(p) and os.path.getsize(p) > 0: return p
    if os.path.exists("cookies"):
        files = [f for f in os.listdir("cookies") if f.endswith(".txt")]
        if files: return os.path.join("cookies", random.choice(files))
    return None

def extract_video_id(link: str) -> str:
    if not link: return ""
    m = YOUTUBE_ID_RE.search(link)
    if m: return m.group(1)
    return link.split("/")[-1].split("?")[0]

def verify_file(file_path: str) -> str:
    """Titanium Integrity Check"""
    if os.path.exists(file_path) and not file_path.endswith(".part"):
        return file_path
    
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    folder = os.path.dirname(file_path)
    
    for _ in range(50):
        if os.path.exists(file_path): return file_path
        if os.path.exists(file_path + ".part"):
            time.sleep(0.1)
            continue
        for f in os.listdir(folder):
            if f.startswith(base_name) and not f.endswith(".part") and not f.endswith(".aria2"):
                return os.path.join(folder, f)
        time.sleep(0.1)
    return file_path 

def get_base_opts() -> Dict:
    opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "continuedl": True,
        "noprogress": True,
        "ignoreerrors": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "socket_timeout": 30, # زيادة المهلة للاتصالات الثقيلة
    }
    if HAS_ARIA2:
        opts["external_downloader"] = "aria2c"
        opts["external_downloader_args"] = ARIA2_ARGS
    
    if cookie := get_cookie_path():
        opts["cookiefile"] = cookie
    return opts


# ==============================================================================
# ⚡ TITANIUM CLASS: YOUTUBE API
# ==============================================================================

class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self.pool = POOL
        LOG.info(f"⚡ TITANIUM ENGINE LOADED. RAM: {DOWNLOAD_DIR} | ARIA2: {HAS_ARIA2}")

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip(): return self.base_url + videoid.strip()
        link = (link or "").strip()
        if "youtu.be" in link: return self.base_url + link.split("/")[-1].split("?")[0]
        if "shorts" in link or "live" in link: return self.base_url + link.split("/")[-1].split("?")[0]
        return link.split("&")[0]

    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        return bool(re.search(r"(?:youtube\.com|youtu\.be)", self._prepare_link(link, videoid)))

    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            if not msg: continue
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset: ent.offset + ent.length].split("&si")[0]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url.split("&si")[0]
        return None

    # --- البحث السريع ---
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        prepared = self._prepare_link(link, videoid)
        async with _meta_lock:
            if prepared in _meta_cache:
                return _meta_cache[prepared]
        try:
            data = await VideosSearch(prepared, limit=1).next()
            info = data["result"][0]
            details = {
                "title": info.get("title", "Unknown"),
                "link": prepared,
                "vidid": info.get("id", ""),
                "duration_min": info.get("duration", "0:00"),
                "thumb": (info.get("thumbnails", [{}])[-1].get("url", "")).split("?")[0],
                "channel": info.get("channel", {}).get("name", "Unknown"),
            }
            async with _meta_lock:
                _meta_cache[prepared] = (details, info.get("id", ""))
            return details, info.get("id", "")
        except:
            return {"title": "Unknown", "link": prepared, "vidid": "error", "duration_min": "0:00", "thumb": ""}, "error"

    async def details(self, link: str, videoid: Union[str, bool, None] = None):
        d, vid = await self.track(link, videoid)
        if vid == "error": return None
        return d["title"], d["duration_min"], time_to_seconds(d["duration_min"]), d["thumb"], vid

    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        d, _ = await self.track(link, videoid)
        return d.get("title", "")

    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        d, _ = await self.track(link, videoid)
        return d.get("duration_min")

    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        d, _ = await self.track(link, videoid)
        return d.get("thumb", "")

    # --- ☢️ محرك التحميل (RAM DISK OPTIMIZED) ☢️ ---
    async def _download_internal(self, link: str, video: bool = False, format_id: str = None) -> Optional[str]:
        prepared = self._prepare_link(link)
        vid = extract_video_id(prepared) or str(int(time.time()))
        loop = asyncio.get_running_loop()

        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(vid) and not f.endswith(".part") and not f.endswith(".aria2"):
                return os.path.join(DOWNLOAD_DIR, f)

        opts = get_base_opts()
        
        # أفضل إعدادات للجودة مع السرعة
        if format_id:
            opts["format"] = format_id
        elif video:
            opts["format"] = "bestvideo+bestaudio/best"
        else:
            opts["format"] = "bestaudio/best"

        def _sync_dl():
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(prepared, download=False)
                    if not info: return None
                    
                    ydl.download([prepared])
                    
                    expected_path = os.path.join(DOWNLOAD_DIR, f"{info['id']}.{info['ext']}")
                    final_path = verify_file(expected_path)
                    
                    if os.path.exists(final_path):
                        return final_path
                        
                    for f in os.listdir(DOWNLOAD_DIR):
                        if f.startswith(vid) and not f.endswith(".aria2") and not f.endswith(".part"):
                            return os.path.join(DOWNLOAD_DIR, f)
                    return None
            except Exception as e:
                LOG.error(f"⚠️ Speed DL Fail: {e}")
                return None

        return await loop.run_in_executor(self.pool, _sync_dl)

    # --- الواجهة العامة ---
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        songaudio: bool = False,
        songvideo: bool = False,
        format_id: str = None,
        title: str = None
    ) -> Tuple[Optional[str], Optional[bool]]:
        
        prepared = self._prepare_link(link, videoid)
        is_video_req = bool(video) or bool(songvideo)
        path = await self._download_internal(prepared, video=is_video_req, format_id=format_id)
        if path: return path, True
        return None, None

    # --- إضافات ---
    async def slider(self, link: str, query_type: int, videoid: Union[str, bool, None] = None):
        try:
            data = await VideosSearch(self._prepare_link(link, videoid), limit=10).next()
            r = data["result"][query_type]
            return r["title"], r["duration"], r["thumbnails"][0]["url"].split("?")[0], r["id"]
        except: return "Error", "0", "", "error"

    async def playlist(self, link, limit, user_id, videoid: Union[str, bool, None] = None):
        if videoid: link = f"https://youtube.com/playlist?list={videoid}"
        cmd = ["yt-dlp", "--flat-playlist", "--get-id", "--playlist-end", str(limit), link]
        if cookie := get_cookie_path(): cmd[1:1] = ["--cookies", cookie]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await proc.communicate()
        return out.decode().splitlines() if out else []

    async def formats(self, link: str, videoid: Union[str, bool, None] = None):
        prepared = self._prepare_link(link, videoid)
        def _get():
            try:
                with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                    r = ydl.extract_info(prepared, download=False)
                    return [{
                        "format": f["format"], "filesize": f.get("filesize") or f.get("filesize_approx"),
                        "format_id": f["format_id"], "ext": f["ext"], "format_note": f.get("format_note"), "yturl": prepared
                    } for f in r.get("formats", []) if f.get("filesize") or f.get("filesize_approx")]
            except: return []
        return await self.pool.submit(_get), prepared

    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        prepared = self._prepare_link(link, videoid)
        cmd = ["yt-dlp", "--force-ipv4", "-g", "-f", "best[ext=mp4]/best", prepared]
        if cookie := get_cookie_path(): cmd[1:1] = ["--cookies", cookie]
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            if stdout: return 1, stdout.decode().splitlines()[0]
            return 0, stderr.decode()
        except Exception as e: return 0, str(e)

# تصدير الكائن
YouTube = YouTubeAPI()
