# Authored By Certified Coders © 2025 (Enhanced)
"""
Ultimate Reverse-Hybrid Downloader — STREAM-FIRST + ARIA2 backup
Behavior:
 - Probe for direct stream URL (fast path). If found -> return "stream://{url}" immediately.
 - Spawn background full-download (yt-dlp with aria2) to produce local cached file.
 - If probe fails, fall back to normal yt-dlp download (fast options + aria2).
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
from typing import Dict, Optional, Tuple

import aiofiles
import aiohttp
from aiohttp import TCPConnector
from yt_dlp import YoutubeDL

# Project imports (keep as in your project)
from AnnieXMedia.core.dir import CACHE_DIR, DOWNLOAD_DIR
from AnnieXMedia.utils.cookie_handler import COOKIE_PATH as _COOKIES_FILE
from AnnieXMedia.utils.tuning import CHUNK_SIZE, SEM
from config import API_KEY, API_URL, VIDEO_API_URL
from AnnieXMedia.logging import LOGGER as EXTERNAL_LOGGER

# Local logger - fallback safe usage
if callable(EXTERNAL_LOGGER):
    log = EXTERNAL_LOGGER(__name__)
else:
    log = logging.getLogger(__name__)

# --- Configuration ---
USE_AUDIO_API = bool(API_URL and API_KEY)
USE_VIDEO_API = bool(VIDEO_API_URL and API_KEY)
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
ARIA2_PATH = shutil.which("aria2c")

# --- Directories Setup ---
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


# ---------------- Cache Manager ----------------

async def register_cache(path: str) -> None:
    if not path or not os.path.exists(path): return
    abs_path = os.path.abspath(path)
    try:
        async with _cache_lock:
            _cache_registry[abs_path] = time.time() + CACHE_TTL
    except Exception:
        pass

def _register_cache_sync(path: str) -> None:
    if not path: return
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
    log.info("Cache Cleaner Started 🧹")
    while True:
        await asyncio.sleep(60)
        now = time.time()
        to_delete = []
        async with _cache_lock:
            for path, expiry in list(_cache_registry.items()):
                if now > expiry:
                    to_delete.append(path)
        for path in to_delete:
            try:
                if os.path.exists(path): os.remove(path)
                async with _cache_lock:
                    _cache_registry.pop(path, None)
            except Exception:
                pass

def init_cache_cleaner():
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_cache_cleaner_loop())
    except Exception:
        pass


# ---------------- Helpers ----------------

def _safe_filename(title: str) -> str:
    if not title: return str(int(time.time()))
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
    if not vid: return None
    target_dir = AUDIO_DIR if kind == "audio" else VIDEO_DIR
    pattern = os.path.join(target_dir, f"{vid}_*")
    matches = glob.glob(pattern)
    if matches:
        cached = max(matches, key=os.path.getmtime)
        _register_cache_sync(cached)
        return cached
    root_pattern = os.path.join(DOWNLOAD_DIR, f"{vid}.*")
    root_matches = glob.glob(root_pattern)
    if root_matches:
        cached = max(root_matches, key=os.path.getmtime)
        _register_cache_sync(cached)
        return cached
    return None

def _check_result(info, out_dir, fname_base):
    """Internal helper to verify download success."""
    if isinstance(info, dict) and "requested_downloads" in info:
        fpath = info["requested_downloads"][0].get("filepath")
        if fpath and os.path.exists(fpath):
            _register_cache_sync(fpath)
            return fpath
    ext = info.get("ext", "m4a") if isinstance(info, dict) else "m4a"
    expected = os.path.join(out_dir, f"{fname_base}.{ext}")
    if os.path.exists(expected):
        _register_cache_sync(expected)
        return expected
    files = glob.glob(os.path.join(out_dir, f"{fname_base}.*"))
    if files:
        f = max(files, key=os.path.getmtime)
        _register_cache_sync(f)
        return f
    return None


# ---------------- Network / API ----------------

async def get_http_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed: return _session
    async with _session_lock:
        if _session and not _session.closed: return _session
        timeout = aiohttp.ClientTimeout(total=600, sock_connect=15, sock_read=120)
        # high concurrency, keepalive enabled
        connector = TCPConnector(limit=0, ttl_dns_cache=300)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _session

async def download_direct_file(url: str, out_path: str) -> Optional[str]:
    try:
        session = await get_http_session()
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return None
            async with aiofiles.open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    if chunk:
                        await f.write(chunk)
        if os.path.exists(out_path):
            await register_cache(out_path)
            return out_path
    except Exception as e:
        log.debug(f"Direct download failed: {e}")
    return None

async def api_download(link: str, kind: str, title: str) -> Optional[str]:
    vid = extract_video_id(link)
    if not vid: return None
    base_url = VIDEO_API_URL if kind == "video" else API_URL
    endpoint = "video" if kind == "video" else "song"
    if not base_url or not API_KEY:
        return None
    poll_url = f"{base_url}/{endpoint}/{vid}?api={API_KEY}"
    try:
        session = await get_http_session()
        for _ in range(30):
            async with session.get(poll_url) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                status = str(data.get("status", "")).lower()
                if status == "done":
                    fmt = data.get("format", "mp4" if kind == "video" else "m4a")
                    fname = f"{vid}_{kind}_{_safe_filename(title)}.{fmt}"
                    out_path = os.path.join(VIDEO_DIR if kind == "video" else AUDIO_DIR, fname)
                    return await download_direct_file(data.get("link"), out_path)
                if status == "error":
                    return None
                await asyncio.sleep(1)
    except Exception as e:
        log.debug(f"api_download error: {e}")
    return None


# ---------------- Probe & Stream Helpers (SYNC functions to run in executor) ----------------

def _build_base_opts(out_dir: str, final_filename: str, kind: str) -> dict:
    outtmpl = os.path.join(out_dir, f"{final_filename}.%(ext)s")
    base_opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "continuedl": True,
        "overwrites": False,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "source_address": "0.0.0.0",  # force IPv4
        "cachedir": str(CACHE_DIR),
        "retries": 5,
        "socket_timeout": 15,
        "prefer_ffmpeg": True,
    }
    if cookie := get_cookie_file():
        base_opts["cookiefile"] = cookie

    if kind == "audio":
        # try to prefer M4A low bitrate (fast)
        base_opts["format"] = "bestaudio[ext=m4a][abr<=128]/bestaudio/best"
    else:
        base_opts["format"] = "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    return base_opts

def probe_stream_url_sync(link: str, kind: str) -> Optional[str]:
    """
    Light-weight probe: use yt-dlp to extract formats (no download) and return a direct URL
    for a good audio format (prefer m4a abr<=128) OR bestaudio url.
    """
    vid = extract_video_id(link) or _make_link_id(link)
    out_dir = AUDIO_DIR if kind == "audio" else VIDEO_DIR
    final_filename = f"{vid}_{kind}_probe"
    opts = _build_base_opts(out_dir, final_filename, kind)
    opts.update({
        "skip_download": True,
        "quiet": True,
        "simulate": True,
        "forcejson": True,
    })
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=False)
            # Prefer direct url from entries/formats
            if isinstance(info, dict):
                # if 'url' present in format selection, use it
                fmt = None
                if "formats" in info and info["formats"]:
                    # choose best candidate m4a with abr<=128 then bestaudio
                    for f in reversed(sorted(info["formats"], key=lambda x: x.get("abr") or 0)):
                        ext = f.get("ext") or ""
                        abr = f.get("abr") or 0
                        if ext == "m4a" and abr and abr <= 160:
                            fmt = f
                            break
                    if fmt is None:
                        # fallback to bestaudio
                        for f in reversed(sorted(info["formats"], key=lambda x: x.get("abr") or 0)):
                            if "audio" in f.get("acodec", "") or f.get("vcodec", "none") == "none":
                                fmt = f
                                break
                    if fmt and fmt.get("url"):
                        return fmt.get("url")
                # if "url" at root:
                if info.get("url"):
                    return info.get("url")
    except Exception as e:
        # probe may fail silently
        log.debug(f"probe_stream_url_sync failed for {link}: {e}")
    return None

def download_sync_ytdlp(link: str, kind: str, title_hint: str) -> Optional[str]:
    """
    Full synchronous downloader (called inside executor).
    Uses yt-dlp with aria2 backup if available.
    Returns local file path on success or None.
    """
    vid = extract_video_id(link) or _make_link_id(link)
    out_dir = AUDIO_DIR if kind == "audio" else VIDEO_DIR
    safe_title = _safe_filename(title_hint)
    final_filename = f"{vid}_{kind}_{safe_title}"
    base_opts = _build_base_opts(out_dir, final_filename, kind)

    # performance-tuning around fragments / chunking
    native_opts = base_opts.copy()
    native_opts.update({
        "concurrent_fragment_downloads": 4,
        "http_chunk_size": 4 * 1024 * 1024,  # 4MB
        "buffersize": 4 * 1024 * 1024,
        "fragment_retries": 3,
    })

    try:
        with YoutubeDL(native_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            if result := _check_result(info, out_dir, final_filename):
                return result
    except Exception as e:
        log.warning(f"Direct Stream/Native download failed ({e}). Trying aria2 backup...")

    # aria2 backup
    if ARIA2_PATH:
        aria_opts = base_opts.copy()
        aria_opts["external_downloader"] = "aria2c"
        aria_opts["external_downloader_args"] = [
            "-x", "16", "-s", "16", "-k", "1M", "--file-allocation=none"
        ]
        try:
            with YoutubeDL(aria_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                if result := _check_result(info, out_dir, final_filename):
                    return result
        except Exception as e:
            log.error(f"Aria2 backup failed: {e}")
    return None


# ---------------- Async Management ----------------

async def run_with_semaphore(coro):
    async with SEM:
        return await coro

async def deduplicate_download(key: str, runner):
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

async def _schedule_background_full_download(loop, link, kind, title):
    """Schedule a full download in background (runs in executor)."""
    try:
        # don't block: run full downloader in executor
        await loop.run_in_executor(None, download_sync_ytdlp, link, kind, title)
    except Exception as e:
        log.debug(f"Background full download failed: {e}")

async def race_tasks(yt_task, api_task, title: str, kind: str):
    """Race API vs yt-dlp (tasks are asyncio.Tasks)"""
    tasks = {t for t in (yt_task, api_task) if t}
    if not tasks: return None

    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    for t in done:
        try:
            res = t.result()
            if res:
                # treat stream:// as success too
                if isinstance(res, str) and res.startswith("stream://"):
                    log.info(f"⚡ Fast stream available for '{title}' ({kind})")
                    for p in pending: p.cancel()
                    return res
                if os.path.exists(res):
                    src = "API" if t is api_task else "yt-dlp"
                    log.info(f"⚡ Downloaded '{title}' via {src} ({kind})")
                    for p in pending: p.cancel()
                    return res
        except Exception:
            pass

    # if first completed didn't return usable, await others
    for p in pending:
        try:
            res = await p
            if res:
                if isinstance(res, str) and res.startswith("stream://"):
                    return res
                if os.path.exists(res):
                    return res
        except Exception:
            pass
    return None


# ---------------- Public Interface ----------------

async def yt_dlp_download(link: str, type: str, title: str = "") -> Optional[str]:
    """
    Main async entry:
    - If probe yields direct stream URL -> returns "stream://{url}" immediately (fast path).
      Also schedules background download to cache the file locally.
    - Otherwise, performs full download and returns local file path.
    """
    loop = asyncio.get_event_loop()
    kind = "audio" if type == "audio" else "video"

    vid = extract_video_id(link)
    id_key = vid if vid else _make_link_id(link)

    # 1. Check Cache
    if vid and (cached := find_cached_file(vid, kind)):
        log.info(f"📦 Cache Hit: '{title}' ({kind})")
        return cached

    key = f"{kind}:{id_key}"

    async def runner():
        # First: try probe (fast)
        probe_future = loop.run_in_executor(None, probe_stream_url_sync, link, kind)
        probe_task = asyncio.create_task(run_with_semaphore(probe_future))

        # Prepare API task if available
        api_task = None
        if kind == "audio" and USE_AUDIO_API:
            api_task = asyncio.create_task(api_download(link, "audio", title))
        elif kind == "video" and USE_VIDEO_API:
            api_task = asyncio.create_task(api_download(link, "video", title))

        # Also prepare fallback full-download task but don't start it until needed
        # We'll start real full-download only if probe fails after short wait or API loses
        # For now, we race probe + api
        res = await race_tasks(probe_task, api_task, title or id_key, kind)
        if res:
            # Fast path: direct stream URL
            if isinstance(res, str) and res.startswith("stream://"):
                # schedule background full download to get cached file
                loop.create_task(_schedule_background_full_download(loop, link, kind, title))
                return res
            # API or file path returned
            return res

        # If no fast result -> run full synchronous download (blocking in executor)
        full_future = loop.run_in_executor(None, download_sync_ytdlp, link, kind, title)
        full_res = await run_with_semaphore(full_future)
        return full_res

    # Execute with dedupe
    result = await deduplicate_download(key, runner)
    if result:
        # If returned stream marker, we don't have cached path yet
        if isinstance(result, str) and result.startswith("stream://"):
            # we still register nothing but return marker
            return result
        await register_cache(result)
    return result

# Initialize cleaner on import
init_cache_cleaner()
