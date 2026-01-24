# Authored By Certified Coders © 2026
# TITANIUM GOD MODE: INFINITY EDITION ♾️
# SPECS: 50GB RAM | 2.6Gbps NETWORK
# FEATURES: INSTANT START | SPEEDOMETER (10s) | LONG VIDEO SUPPORT

import asyncio
import logging
import os
import re
import shutil
import time
import random
import socket
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple, Union

# --- 1. CORE NETWORK OPTIMIZATION ---
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

try:
    import ujson as json
except ImportError:
    import json

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.aio import Playlist, VideosSearch

# --- 2. IMPORTS & UTILS ---
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

# --- 3. RAM DISK SETUP ---
try:
    from AnnieXMedia.core.dir import DOWNLOAD_DIR
except ImportError:
    if os.path.exists("/dev/shm"):
        DOWNLOAD_DIR = os.path.join("/dev/shm", "AnnieX_Titanium")
    else:
        DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- 4. LOGGING ---
logging.getLogger("yt_dlp").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
LOG = logging.getLogger("Titan_Infinity")

# 256 Threads for Massive Parallelism
POOL = ThreadPoolExecutor(max_workers=256)

# --- 5. DNS PREFETCH (تسخين الاتصال) ---
def prefetch_dns():
    try:
        socket.gethostbyname("www.youtube.com")
        socket.gethostbyname("googlevideo.com")
        LOG.info("⚡ DNS PREFETCH: READY (0ms Latency)")
    except: pass
prefetch_dns()

# --- 6. ARIA2 ENGINE (LONG VIDEO OPTIMIZED) ---
HAS_ARIA2 = shutil.which("aria2c") is not None
ARIA2_ARGS = [
    "-c", 
    "-x", "16",            # 16 Connections
    "-s", "16",            # 16 Splits
    "-j", "50",            # Parallel Downloads
    "-k", "16M",           # 16MB Chunk (Best for high speed & long videos)
    "--min-split-size=8M", 
    "--file-allocation=none", 
    "--quiet=true", 
    "--connect-timeout=5", 
    "--max-tries=10",      # محاولات أكتر للفيديوهات الطويلة
    "--disk-cache=1024M",  # 1GB Cache
    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

_meta_cache: Dict[str, Tuple[float, Dict]] = {}
_meta_lock = asyncio.Lock()
YOUTUBE_ID_RE = re.compile(r"(?:v=|\/)([A-Za-z0-9_-]{11})")

# ==============================================================================
# ⏱️ SPEEDOMETER (عداد السرعة)
# ==============================================================================

async def monitor_speed(start_time, file_prefix):
    """
    مراقب السرعة: يطبع تقرير كل 10 ثواني
    """
    last_log_time = time.time()
    last_size = 0
    
    # انتظار بدء الملف
    while True:
        if time.time() - start_time > 15: return # Timeout wait
        found = False
        target_file = ""
        # البحث عن الملف أو الجزء (.part)
        folder = os.path.dirname(file_prefix)
        base = os.path.basename(file_prefix)
        for f in os.listdir(folder):
            if f.startswith(base):
                target_file = os.path.join(folder, f)
                found = True
                break
        if found: break
        await asyncio.sleep(0.5)

    LOG.info(f"🚀 DOWNLOAD STARTED: {os.path.basename(target_file)}")

    while True:
        await asyncio.sleep(1)
        # لو الملف خلص (مفيش .part ومفيش .aria2)
        if not os.path.exists(target_file) and not any(f.endswith((".part", ".aria2")) for f in os.listdir(folder) if f.startswith(base)):
            break
            
        current_time = time.time()
        if current_time - last_log_time >= 10: # كل 10 ثواني
            try:
                current_size = 0
                # جمع حجم الملفات المؤقتة
                for f in os.listdir(folder):
                    if f.startswith(base):
                        current_size += os.path.getsize(os.path.join(folder, f))
                
                if current_size > last_size:
                    speed_mbps = ((current_size - last_size) / 1024 / 1024) / 10 # MB/s averages over 10s
                    total_mb = current_size / 1024 / 1024
                    elapsed = current_time - start_time
                    LOG.info(f"📊 MONITOR [10s]: Size: {total_mb:.1f}MB | Time: {elapsed:.0f}s")
                    last_size = current_size
                    last_log_time = current_time
            except: pass

# ==============================================================================
# 🧠 HYDRA STRATEGIES
# ==============================================================================

def get_config(mode: str, cookie_path: str = None) -> Dict:
    opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
        "quiet": True, 
        "no_warnings": True,
        "noplaylist": True,
        "noprogress": True,
        "ignoreerrors": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "socket_timeout": 60, # 60 ثانية للفيديوهات الطويلة عشان ميفصلش
        "concurrent_fragment_downloads": 16,
        "cookiefile": cookie_path,
        "ignore_no_formats_error": True,
    }

    if HAS_ARIA2:
        opts["external_downloader"] = "aria2c"
        opts["external_downloader_args"] = ARIA2_ARGS

    if mode == "android":
        opts.update({
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"],
                    "skip": ["dash", "hls"], 
                    "player_skip": ["configs"], # Enabled JS for solving challenges
                }
            },
            "format": "bestaudio/best",
        })
    elif mode == "ios":
        opts.update({
            "extractor_args": {"youtube": {"player_client": ["ios"]}},
            "format": "bestaudio/best",
        })
    elif mode == "desktop":
        opts.update({
            "extractor_args": {"youtube": {"player_client": ["web"]}},
            "format": "bestaudio/best",
        })

    return opts

# ==============================================================================
# 🛠️ HELPER FUNCTIONS
# ==============================================================================

def get_cookie_path() -> Optional[str]:
    paths = [
        os.path.join(os.getcwd(), "AnnieXMedia", "assets", "cookies.txt"),
        os.path.join(os.getcwd(), "cookies.txt"),
        str(COOKIE_PATH) if COOKIE_PATH else ""
    ]
    for p in paths:
        if p and os.path.exists(p) and os.path.getsize(p) > 0: return p
    return None

def verify_file(file_path: str) -> str:
    if os.path.exists(file_path) and not file_path.endswith(".part"): return file_path
    base = os.path.splitext(os.path.basename(file_path))[0]
    folder = os.path.dirname(file_path)
    for _ in range(50):
        if os.path.exists(file_path): return file_path
        for f in os.listdir(folder):
            if f.startswith(base) and not f.endswith((".part", ".aria2")):
                return os.path.join(folder, f)
        time.sleep(0.1)
    return file_path 

# ==============================================================================
# ⚡ YOUTUBE API CLASS
# ==============================================================================

class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.pool = POOL
        self.cookie = get_cookie_path()
        LOG.info(f"⚡ TITANIUM INFINITY READY | 2.6Gbps | COOKIE: {'✅' if self.cookie else '❌'}")

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip(): return self.base_url + videoid.strip()
        link = (link or "").strip()
        if "youtu.be" in link: return self.base_url + link.split("/")[-1].split("?")[0]
        return link.split("&")[0]

    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            if not msg: continue
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for ent in entities:
                if ent.type == MessageEntityType.URL: return text[ent.offset: ent.offset + ent.length].split("&")[0]
                if ent.type == MessageEntityType.TEXT_LINK: return ent.url.split("&")[0]
        return None

    # --- البحث ---
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        prepared = self._prepare_link(link, videoid)
        async with _meta_lock:
            if prepared in _meta_cache: return _meta_cache[prepared]
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
            async with _meta_lock: _meta_cache[prepared] = (details, info.get("id", ""))
            return details, info.get("id", "")
        except: return {"title": "Unknown", "link": prepared, "vidid": "error", "duration_min": "0:00", "thumb": ""}, "error"

    async def details(self, link, videoid=None):
        d, v = await self.track(link, videoid)
        return (d["title"], d["duration_min"], time_to_seconds(d["duration_min"]), d["thumb"], v) if v != "error" else None

    async def title(self, link, videoid=None): return (await self.track(link, videoid))[0].get("title", "")
    async def duration(self, link, videoid=None): return (await self.track(link, videoid))[0].get("duration_min")
    async def thumbnail(self, link, videoid=None): return (await self.track(link, videoid))[0].get("thumb", "")

    # --- ☢️ DIRECT INJECTION DOWNLOADER ☢️ ---
    async def _download_internal(self, link: str, video: bool = False, format_id: str = None) -> Optional[str]:
        start_time = time.time()
        prepared = self._prepare_link(link)
        try:
            vid = prepared.split("v=")[1].split("&")[0]
        except:
            vid = str(int(time.time()))
        
        loop = asyncio.get_running_loop()

        # 1. RAM Cache Check
        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(vid) and not f.endswith((".part", ".aria2")):
                LOG.info(f"✅ INSTANT CACHE HIT: 0.0s")
                return os.path.join(DOWNLOAD_DIR, f)

        # 2. Strategies
        strategies = ["android", "ios", "desktop"]
        
        def _execute_strategy(mode):
            try:
                opts = get_config(mode, self.cookie)
                if format_id: opts["format"] = format_id
                elif video: opts["format"] = "bestvideo+bestaudio/best"
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    # 🔥 DIRECT INJECTION: download=True فوراً
                    info = ydl.extract_info(prepared, download=True)
                    expected = os.path.join(DOWNLOAD_DIR, f"{info['id']}.{info['ext']}")
                    return expected
            except Exception as e:
                LOG.error(f"⚠️ Strategy {mode} Failed: {e}")
                return None

        def _smart_dl_manager():
            for strategy in strategies:
                LOG.info(f"🚀 Launching Strategy: {strategy.upper()}...")
                
                # تشغيل العداد في الخلفية
                expected_temp = os.path.join(DOWNLOAD_DIR, vid)
                asyncio.run_coroutine_threadsafe(monitor_speed(start_time, expected_temp), loop)

                result = _execute_strategy(strategy)
                
                final_path = verify_file(os.path.join(DOWNLOAD_DIR, vid))
                if os.path.exists(final_path):
                    total_time = time.time() - start_time
                    LOG.info(f"✅ DONE | {strategy} | TIME: {total_time:.2f}s | FILE: {os.path.basename(final_path)}")
                    return final_path
            return None

        return await loop.run_in_executor(self.pool, _smart_dl_manager)

    # --- Public Methods ---
    async def download(self, link, mystic, *, video=None, videoid=None, songaudio=False, songvideo=False, format_id=None, title=None):
        prepared = self._prepare_link(link, videoid)
        is_video = bool(video) or bool(songvideo)
        path = await self._download_internal(prepared, video=is_video, format_id=format_id)
        return (path, True) if path else (None, None)

    async def slider(self, link, query_type, videoid=None):
        try:
            data = await VideosSearch(self._prepare_link(link, videoid), limit=10).next()
            r = data["result"][query_type]
            return r["title"], r["duration"], r["thumbnails"][0]["url"].split("?")[0], r["id"]
        except: return "Error", "0", "", "error"

    async def playlist(self, link, limit, user_id, videoid=None):
        if videoid: link = f"https://youtube.com/playlist?list={videoid}"
        cmd = ["yt-dlp", "--flat-playlist", "--get-id", "--playlist-end", str(limit), link]
        if self.cookie: cmd[1:1] = ["--cookies", self.cookie]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await proc.communicate()
        return out.decode().splitlines() if out else []

    async def formats(self, link, videoid=None):
        prepared = self._prepare_link(link, videoid)
        def _get():
            try:
                with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                    r = ydl.extract_info(prepared, download=False)
                    return [{
                        "format": f["format"], "filesize": f.get("filesize") or f.get("filesize_approx"),
                        "format_id": f["format_id"], "ext": f["ext"], "format_note": f.get("format_note"), "yturl": prepared
                    } for f in r.get("formats", [])]
            except: return []
        return await self.pool.submit(_get), prepared

    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        prepared = self._prepare_link(link, videoid)
        cmd = ["yt-dlp", "--force-ipv4", "-g", "-f", "best[ext=mp4]/best", prepared]
        if self.cookie: cmd[1:1] = ["--cookies", self.cookie]
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            if stdout: return 1, stdout.decode().splitlines()[0]
            return 0, stderr.decode()
        except Exception as e: return 0, str(e)

# Export
YouTube = YouTubeAPI()
