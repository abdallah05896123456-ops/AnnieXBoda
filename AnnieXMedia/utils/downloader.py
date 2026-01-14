# Authored By Certified Coders © 2025
"""
Extreme Speed Downloader:
Combines the robustness of Annie/Smart-Code with the raw speed of Alexa.
- Formats: Prefers M4A (No conversion needed = Instant).
- Threads: Runs in Executor.
- Cache: Separate folders (audio/video), smart TTL, auto-clean.
- Network: Optimized cookie handling & bypasses.
"""

import asyncio
import contextlib
import glob
import os
import re
import shutil
import time
import hashlib
import html
import logging
from typing import Dict, Optional

import aiofiles
import aiohttp
from aiohttp import TCPConnector
from yt_dlp import YoutubeDL

# تأكد من أن المسارات صحيحة في ملف core/dir.py
from AnnieXMedia.core.dir import CACHE_DIR, DOWNLOAD_DIR
from AnnieXMedia.utils.cookie_handler import COOKIE_PATH as _COOKIES_FILE
from AnnieXMedia.utils.tuning import CHUNK_SIZE, SEM
from config import API_KEY, API_URL, VIDEO_API_URL
from AnnieXMedia.logging import LOGGER

LOGGER = LOGGER(__name__)

# --- Configuration ---
USE_AUDIO_API = bool(API_URL and API_KEY)
USE_VIDEO_API = bool(VIDEO_API_URL and API_KEY)
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
ARIA2_PATH = shutil.which("aria2c")

# --- Directories Setup ---
# إنشاء مجلدات منفصلة للصوت والفيديو لتنظيم الكاش
AUDIO_DIR = os.path.join(DOWNLOAD_DIR, "audio")
VIDEO_DIR = os.path.join(DOWNLOAD_DIR, "video")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

# --- State Management ---
_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()

_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()

# Cache settings (10 Minutes TTL)
CACHE_TTL = 600
_cache_registry: Dict[str, float] = {}
_cache_lock = asyncio.Lock()


# ---------------- Cache Manager (Fixed & Optimized) ----------------

async def register_cache(path: str) -> None:
    """Register a file in cache to prevent deletion."""
    if not path or not os.path.exists(path):
        return
    # استخدام المسار المطلق لتجنب أخطاء المسارات
    abs_path = os.path.abspath(path)
    try:
        async with _cache_lock:
            _cache_registry[abs_path] = time.time() + CACHE_TTL
    except Exception:
        pass

def _register_cache_sync(path: str) -> None:
    """Sync wrapper for cache registration (called from threads)."""
    if not path:
        return
    abs_path = os.path.abspath(path)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(asyncio.create_task, register_cache(abs_path))
        else:
            _cache_registry[abs_path] = time.time() + CACHE_TTL
    except Exception:
        pass

async def _cache_cleaner_loop() -> None:
    """Background task to clean old files."""
    LOGGER.info("Cache Cleaner Started 🧹")
    while True:
        await asyncio.sleep(60)  # Check every minute
        now = time.time()
        to_delete = []
        
        async with _cache_lock:
            for path, expiry in list(_cache_registry.items()):
                if now > expiry:
                    to_delete.append(path)
        
        for path in to_delete:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    LOGGER.debug(f"Cache Cleaner: Removed {os.path.basename(path)}")
                async with _cache_lock:
                    _cache_registry.pop(path, None)
            except Exception as e:
                LOGGER.debug(f"Failed to delete {path}: {e}")

def init_cache_cleaner():
    """Start the cleaner loop."""
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_cache_cleaner_loop())
    except Exception:
        pass


# ---------------- Helpers ----------------

def _safe_filename(title: str) -> str:
    """Generate a safe filename from title."""
    if not title:
        return str(int(time.time()))
    s = html.unescape(title)
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "_", s.strip())
    return s[:50]

def extract_video_id(link: str) -> str:
    if not link: return ""
    s = link.strip()
    if YOUTUBE_ID_RE.match(s): return s
    if "v=" in s: return s.split("v=")[-1].split("&")[0]
    last = s.split("/")[-1].split("?")[0]
    return last if YOUTUBE_ID_RE.match(last) else ""

def _make_link_id(link: str) -> str:
    return hashlib.md5(link.encode()).hexdigest()[:16]

def get_cookie_file() -> Optional[str]:
    if _COOKIES_FILE and os.path.exists(_COOKIES_FILE) and os.path.getsize(_COOKIES_FILE) > 0:
        return _COOKIES_FILE
    return None

def find_cached_file(vid: str, kind: str) -> Optional[str]:
    """Search for cached file in organized folders."""
    if not vid: return None
    target_dir = AUDIO_DIR if kind == "audio" else VIDEO_DIR
    
    # البحث عن أي ملف يبدأ بالـ ID في المجلد المحدد
    pattern = os.path.join(target_dir, f"{vid}_*")
    matches = glob.glob(pattern)
    
    if matches:
        # إرجاع أحدث ملف تم تعديله
        cached = max(matches, key=os.path.getmtime)
        _register_cache_sync(cached)
        return cached
    
    # Legacy fallback (root folder)
    root_pattern = os.path.join(DOWNLOAD_DIR, f"{vid}.*")
    root_matches = glob.glob(root_pattern)
    if root_matches:
        cached = max(root_matches, key=os.path.getmtime)
        _register_cache_sync(cached)
        return cached
        
    return None


# ---------------- Network / API ----------------

async def get_http_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    async with _session_lock:
        if _session and not _session.closed:
            return _session
        timeout = aiohttp.ClientTimeout(total=600, sock_connect=10, sock_read=60)
        connector = TCPConnector(limit=0, ttl_dns_cache=300)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _session

async def download_direct_file(url: str, out_path: str) -> Optional[str]:
    try:
        session = await get_http_session()
        async with session.get(url) as resp:
            if resp.status != 200: return None
            async with aiofiles.open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    if chunk: await f.write(chunk)
        if os.path.exists(out_path):
            await register_cache(out_path)
            return out_path
    except Exception:
        pass
    return None

# ---------------- API Wrappers ----------------

async def api_download(link: str, kind: str, title: str) -> Optional[str]:
    """Generic API downloader for both audio and video."""
    vid = extract_video_id(link)
    if not vid: return None
    
    base_url = VIDEO_API_URL if kind == "video" else API_URL
    endpoint = "video" if kind == "video" else "song"
    
    if not base_url or not API_KEY: return None
    
    poll_url = f"{base_url}/{endpoint}/{vid}?api={API_KEY}"
    try:
        session = await get_http_session()
        # محاولة لمدة 30 ثانية فقط ثم الاستسلام لـ yt-dlp
        for _ in range(30): 
            async with session.get(poll_url) as r:
                if r.status != 200: return None
                data = await r.json()
                status = str(data.get("status", "")).lower()
                
                if status == "done":
                    fmt = data.get("format", "mp4" if kind == "video" else "m4a")
                    fname = f"{vid}_{kind}_{_safe_filename(title)}.{fmt}"
                    out_path = os.path.join(VIDEO_DIR if kind == "video" else AUDIO_DIR, fname)
                    return await download_direct_file(data.get("link"), out_path)
                
                if status == "error": return None
                await asyncio.sleep(1)
    except Exception:
        pass
    return None


# ---------------- Core Downloader (The Hybrid Engine) ----------------

def download_sync_ytdlp(link: str, kind: str, title_hint: str) -> Optional[str]:
    """
    Synchronous worker - Runs inside Executor.
    Uses Alexa's format logic + Annie's file organization.
    """
    vid = extract_video_id(link) or _make_link_id(link)
    out_dir = AUDIO_DIR if kind == "audio" else VIDEO_DIR
    safe_title = _safe_filename(title_hint)
    
    # اسم الملف النهائي المتوقع
    final_filename = f"{vid}_{kind}_{safe_title}"
    outtmpl = os.path.join(out_dir, f"{final_filename}.%(ext)s")

    # 🚀 Alexa's Speed Settings 🚀
    opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "continuedl": True,
        "overwrites": False,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "source_address": "0.0.0.0",
        "cachedir": str(CACHE_DIR),
        "retries": 5,
        "socket_timeout": 10,
        "prefer_ffmpeg": True, # استخدام ffmpeg للدمج
    }

    if cookie := get_cookie_file():
        opts["cookiefile"] = cookie

    # ✅ اختيار الصيغة الأسرع (Alexa Style)
    if kind == "audio":
        # m4a لا يحتاج تحويل (سريع جداً)
        opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
    else:
        # فيديو بجودة مناسبة وسرعة عالية
        opts["format"] = "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best"

    # ✅ إعداد Aria2 (فقط إذا لم يكن يوتيوب)
    # Aria2 مع يوتيوب يسبب 403 Errors وتبطئ العملية أحياناً
    if ARIA2_PATH and not ("youtube.com" in link or "youtu.be" in link):
        opts["external_downloader"] = "aria2c"
        opts["external_downloader_args"] = ["-x", "8", "-k", "1M", "-s", "8"]

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=True)
            
            # محاولة العثور على الملف الذي تم تنزيله
            if isinstance(info, dict):
                # الطريقة 1: من requested_downloads
                if info.get("requested_downloads"):
                    fpath = info["requested_downloads"][0].get("filepath")
                    if fpath and os.path.exists(fpath):
                        _register_cache_sync(fpath)
                        return fpath
                
                # الطريقة 2: التخمين بناءً على الامتداد
                ext = info.get("ext", "m4a" if kind == "audio" else "mp4")
                possible_path = os.path.join(out_dir, f"{final_filename}.{ext}")
                if os.path.exists(possible_path):
                    _register_cache_sync(possible_path)
                    return possible_path

            # الطريقة 3: البحث العام
            files = glob.glob(os.path.join(out_dir, f"{final_filename}.*"))
            if files:
                f = max(files, key=os.path.getmtime)
                _register_cache_sync(f)
                return f

    except Exception as e:
        LOGGER.error(f"Download Failed ({kind}): {e}")
        return None


# ---------------- Async Management ----------------

async def run_with_semaphore(coro):
    async with SEM:
        return await coro

async def deduplicate_download(key: str, runner):
    """Prevents downloading the same song twice simultaneously."""
    async with _inflight_lock:
        if fut := _inflight.get(key):
            return await fut
        fut = asyncio.get_running_loop().create_future()
        _inflight[key] = fut
    
    try:
        result = await runner()
        fut.set_result(result)
        return result
    except Exception as e:
        fut.set_exception(e)
        return None
    finally:
        async with _inflight_lock:
            _inflight.pop(key, None)

async def race_tasks(yt_task, api_task, title: str, kind: str):
    """Race API vs yt-dlp. Winner takes all."""
    tasks = {t for t in (yt_task, api_task) if t}
    if not tasks: return None
    
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    
    for t in done:
        try:
            res = t.result()
            if res and os.path.exists(res):
                src = "API" if t is api_task else "yt-dlp"
                LOGGER.info(f"⚡ Downloaded '{title}' via {src} ({kind})")
                for p in pending: p.cancel()
                return res
        except Exception:
            pass
            
    # If first failed, wait for second
    for p in pending:
        try:
            res = await p
            if res and os.path.exists(res):
                src = "API" if p is api_task else "yt-dlp"
                LOGGER.info(f"⚡ Downloaded '{title}' via {src} ({kind})")
                return res
        except Exception:
            pass
            
    return None


# ---------------- Public Interface ----------------

async def yt_dlp_download(link: str, type: str, title: str = "") -> Optional[str]:
    """
    Main entry point.
    - Check Cache -> Race API vs yt-dlp -> Return path
    """
    loop = asyncio.get_running_loop()
    kind = "audio" if type == "audio" else "video"
    
    # 1. ID Check
    vid = extract_video_id(link)
    id_key = vid if vid else _make_link_id(link)
    
    # 2. Check Cache
    if vid and (cached := find_cached_file(vid, kind)):
        LOGGER.info(f"📦 Cache Hit: '{title}' ({kind})")
        return cached

    key = f"{kind}:{id_key}"

    async def runner():
        # Prepare Tasks
        yt_coro = run_with_semaphore(
            loop.run_in_executor(None, download_sync_ytdlp, link, kind, title)
        )
        yt_task = asyncio.create_task(yt_coro)
        
        api_task = None
        if kind == "audio" and USE_AUDIO_API:
            api_task = asyncio.create_task(api_download(link, "audio", title))
        elif kind == "video" and USE_VIDEO_API:
            api_task = asyncio.create_task(api_download(link, "video", title))
            
        return await race_tasks(yt_task, api_task, title or id_key, kind)

    # 3. Execute
    result = await deduplicate_download(key, runner)
    if result:
        await register_cache(result)
    return result

# Initialize cleaner on import
init_cache_cleaner()
