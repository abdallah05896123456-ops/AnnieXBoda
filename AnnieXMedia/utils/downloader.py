# Authored By Certified Coders © 2025
# Architecture: High-Performance Vault & Buffer Streaming Engine
# Features: MD5 Storage, Zero-Copy HLS, Aria2c Acceleration, Auto-Healing

import asyncio
import contextlib
import glob
import os
import re
import hashlib
import time
import shutil
import subprocess
from typing import Dict, Optional, Tuple

import aiofiles
import aiohttp
from aiohttp import TCPConnector
from yt_dlp import YoutubeDL

# --- Import Internal Modules (Do not remove) ---
from AnnieXMedia.core.dir import CACHE_DIR, DOWNLOAD_DIR
from AnnieXMedia.utils.cookie_handler import COOKIE_PATH as _COOKIES_FILE
from AnnieXMedia.utils.tuning import CHUNK_SIZE, SEM
from config import API_KEY, API_URL, VIDEO_API_URL
from AnnieXMedia.logging import LOGGER

LOGGER = LOGGER(__name__)

# --- Configuration & Constants ---
USE_AUDIO_API = bool(API_URL and API_KEY)
USE_VIDEO_API = bool(VIDEO_API_URL and API_KEY)
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
ARIA2_PATH = shutil.which("aria2c")

# --- Directory Architecture (Vault & Buffer) ---
# Vault: تخزين دائم للملفات الخام بأسماء MD5
VAULT_DIR = os.path.join(DOWNLOAD_DIR, "vault")
# Buffer: تخزين مؤقت لملفات البث (HLS)
BUFFER_DIR = os.path.join(DOWNLOAD_DIR, "buffer")

# Ensure directories exist
os.makedirs(VAULT_DIR, exist_ok=True)
os.makedirs(BUFFER_DIR, exist_ok=True)

# --- State Management ---
_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()
_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()


# ==============================================================================
# 1. Identity & Hashing System (نظام التسمية والهاش)
# ==============================================================================

def get_unique_hash(link: str) -> str:
    """Generate MD5 hash for the link to ensure Unique Identity in Vault."""
    return hashlib.md5(link.strip().encode('utf-8')).hexdigest()

def extract_video_id(link: str) -> str:
    """Extract Youtube ID for API compatibility."""
    if not link: return ""
    s = link.strip()
    if YOUTUBE_ID_RE.match(s): return s
    if "v=" in s: return s.split("v=")[-1].split("&")[0]
    last = s.split("/")[-1].split("?")[0]
    if YOUTUBE_ID_RE.match(last): return last
    return ""

def log_download_source(title: str, source: str) -> None:
    LOGGER.info(f"Track '{title}' - Downloaded by {source}")


# ==============================================================================
# 2. Buffer & Maintenance (الصيانة والتنظيف الذاتي)
# ==============================================================================

async def buffer_cleaner_loop(ttl_seconds: int = 600):
    """
    Background Task: Cleans only the 'Buffer' directory.
    Removes HLS files older than 10 minutes (configurable).
    Never touches the 'Vault'.
    """
    LOGGER.info("Buffer Auto-Cleaner Started...")
    while True:
        try:
            now = time.time()
            if os.path.exists(BUFFER_DIR):
                for item in os.listdir(BUFFER_DIR):
                    item_path = os.path.join(BUFFER_DIR, item)
                    # Check modified time
                    if os.path.getmtime(item_path) < (now - ttl_seconds):
                        try:
                            if os.path.isdir(item_path):
                                shutil.rmtree(item_path, ignore_errors=True)
                            else:
                                os.remove(item_path)
                        except Exception as e:
                            LOGGER.debug(f"Failed to clean buffer item {item}: {e}")
            await asyncio.sleep(60)  # Run every minute
        except asyncio.CancelledError:
            break
        except Exception as e:
            LOGGER.error(f"Buffer cleaner exception: {e}")
            await asyncio.sleep(60)

# ==============================================================================
# 3. Transmuxing Engine (HLS & Zero-Copy)
# ==============================================================================

async def convert_to_hls(input_path: str, link_hash: str) -> Optional[str]:
    """
    Converts Raw Vault file (MP4/M4A) to HLS Stream (M3U8) in Buffer.
    Uses 'copy' codec for 0% CPU usage and instant conversion.
    """
    # Create specific buffer folder for this stream
    stream_dir = os.path.join(BUFFER_DIR, link_hash)
    os.makedirs(stream_dir, exist_ok=True)
    output_playlist = os.path.join(stream_dir, "index.m3u8")

    # If already buffered, return immediately
    if os.path.exists(output_playlist):
        return output_playlist

    # FFmpeg Zero-Copy Command
    cmd = [
        'ffmpeg', '-y',
        '-hide_banner', '-loglevel', 'error',
        '-i', input_path,
        '-c', 'copy',          # Critical: No Re-encoding
        '-map', '0',
        '-f', 'hls',
        '-hls_time', '10',     # 10s segments
        '-hls_list_size', '0', # Keep all segments
        '-hls_segment_filename', os.path.join(stream_dir, 'seg_%03d.ts'),
        output_playlist
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        await process.wait()
        
        if process.returncode == 0 and os.path.exists(output_playlist):
            return output_playlist
        return None
    except Exception as e:
        LOGGER.error(f"HLS Conversion Failed: {e}")
        return None


# ==============================================================================
# 4. Network & Session Handling
# ==============================================================================

async def get_http_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    async with _session_lock:
        if _session and not _session.closed:
            return _session
        timeout = aiohttp.ClientTimeout(total=600, sock_connect=20, sock_read=60)
        connector = TCPConnector(limit=0, ttl_dns_cache=300, enable_cleanup_closed=True)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _session

async def close_http_session() -> None:
    global _session
    async with _session_lock:
        if _session and not _session.closed:
            await _session.close()
        _session = None

async def download_file(url: str, out_path: str) -> Optional[str]:
    """Direct HTTP download helper."""
    if not url: return None
    try:
        session = await get_http_session()
        async with session.get(url) as resp:
            if resp.status != 200: return None
            async with aiofiles.open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    if not chunk: break
                    await f.write(chunk)
        return out_path if os.path.exists(out_path) else None
    except Exception:
        return None


# ==============================================================================
# 5. Core Downloader (yt-dlp + Aria2c)
# ==============================================================================

def get_ytdlp_opts(out_path: str) -> Dict[str, object]:
    """
    Returns yt-dlp options optimized for Speed & Vault structure.
    """
    opts = {
        "outtmpl": out_path,  # Force exact path (MD5 name)
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "overwrites": True,
        "continuedl": True,
        "noprogress": True,
        "socket_timeout": 15,
        "retries": 3,
        "cachedir": str(CACHE_DIR),
        "ignoreerrors": True,
        # Force container to MP4 to ensure FFmpeg Zero-Copy compatibility
        "merge_output_format": "mp4", 
    }

    # High-Performance: Enable Aria2c if available
    if ARIA2_PATH:
        opts["external_downloader"] = "aria2c"
        opts["external_downloader_args"] = [
            "-x", "8",   # 8 connections per server
            "-s", "8",   # Split file into 8 parts
            "-k", "1M"   # Min split size
        ]

    if cookiefile := _COOKIES_FILE if os.path.exists(_COOKIES_FILE or "") else None:
        opts["cookiefile"] = cookiefile
    return opts

def download_with_ytdlp_sync(link: str, out_path: str, fmt: str) -> Optional[str]:
    """
    Blocking worker for yt-dlp.
    Downloads to a temp file first, then moves to Vault to ensure atomicity.
    """
    temp_path = f"{out_path}.part"
    try:
        opts = get_ytdlp_opts(temp_path)
        opts["format"] = fmt
        
        with YoutubeDL(opts) as ydl:
            ydl.download([link])
        
        # Determine strict final path (sometimes yt-dlp adds extension despite outtmpl)
        # We need to find the file created at temp_path*
        downloaded_file = None
        if os.path.exists(temp_path):
            downloaded_file = temp_path
        else:
            # Fallback scan for .mp4/.mkv appended
            candidates = glob.glob(f"{temp_path}*")
            if candidates:
                downloaded_file = candidates[0]

        if downloaded_file and os.path.exists(downloaded_file):
            shutil.move(downloaded_file, out_path)
            return out_path
            
    except Exception as e:
        LOGGER.error(f"yt-dlp Sync Error: {e}")
        # Cleanup
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
            
    return None


# ==============================================================================
# 6. Async Orchestration (Race Conditions & Locks)
# ==============================================================================

async def run_with_semaphore(coro):
    async with SEM:
        return await coro

async def deduplicate_download(key: str, runner):
    """
    Asyncio Lock system to prevent 'Thundering Herd' problem 
    when multiple users request the same song simultaneously.
    """
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

async def race_ytdlp_and_api(yt_task, api_task, title: str):
    """
    Parallel Execution: Races internal downloader vs External API.
    Returns the first one to finish successfully.
    """
    tasks = {t for t in (yt_task, api_task) if t}
    if not tasks: return None

    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    for task in done:
        try:
            result = task.result()
            if result and os.path.exists(result):
                source = "yt-dlp" if task is yt_task else "API"
                log_download_source(title, source)
                # Cancel loser tasks
                for p in pending: 
                    p.cancel()
                return result
        except Exception: 
            pass

    # If first failed, wait for others
    for task in pending:
        try:
            result = await task
            if result and os.path.exists(result):
                source = "yt-dlp" if task is yt_task else "API"
                log_download_source(title, source)
                return result
        except Exception: 
            pass
            
    return None


# ==============================================================================
# 7. API Wrappers
# ==============================================================================

async def api_download_audio(link: str, out_path: str) -> Optional[str]:
    if not USE_AUDIO_API: return None
    vid = extract_video_id(link)
    if not vid: return None
    try:
        poll_url = f"{API_URL}/song/{vid}?api={API_KEY}"
        session = await get_http_session()
        # Polling loop (max 30s)
        for _ in range(30):
            async with session.get(poll_url) as r:
                if r.status != 200: return None
                data = await r.json()
                status = data.get("status", "").lower()
                
                if status == "done":
                    return await download_file(data.get("link"), out_path)
                elif status == "error":
                    return None
            await asyncio.sleep(1)
    except Exception:
        pass
    return None

async def api_download_video(link: str, out_path: str) -> Optional[str]:
    if not USE_VIDEO_API: return None
    vid = extract_video_id(link)
    if not vid: return None
    try:
        poll_url = f"{VIDEO_API_URL}/video/{vid}?api={API_KEY}"
        session = await get_http_session()
        # Polling loop (max 60s)
        for _ in range(60):
            async with session.get(poll_url) as r:
                if r.status != 200: return None
                data = await r.json()
                status = data.get("status", "").lower()
                
                if status == "done":
                    return await download_file(data.get("link"), out_path)
            await asyncio.sleep(1)
    except Exception:
        pass
    return None


# ==============================================================================
# 8. Main Entry Point
# ==============================================================================

async def yt_dlp_download(link: str, type: str, title: str = "") -> Optional[str]:
    """
    Main Interface:
    1. Checks Vault for MD5 match.
    2. If missing, races (yt-dlp + aria2) vs API.
    3. Saves to Vault.
    4. (Implicitly ready for generate_hls usage).
    """
    loop = asyncio.get_running_loop()
    
    # 1. Identity Generation
    link_hash = get_unique_hash(link)
    
    # Strict container enforcement for Vault
    target_ext = "m4a" if type == "audio" else "mp4"
    vault_path = os.path.join(VAULT_DIR, f"{link_hash}.{target_ext}")

    # 2. Check Vault (Fast Path)
    if os.path.exists(vault_path) and os.path.getsize(vault_path) > 0:
        if title: 
            LOGGER.info(f"Vault Hit: '{title}' ({type})")
        return vault_path

    # 3. Download Logic (Slow Path)
    key = f"{type}:{link_hash}"

    async def run_download_logic():
        # Setup Tasks
        if type == "audio":
            # Audio: prefer M4A for AAC compatibility
            fmt = "bestaudio[ext=m4a]/bestaudio/best"
            yt_task = asyncio.create_task(run_with_semaphore(
                loop.run_in_executor(None, download_with_ytdlp_sync, link, vault_path, fmt)
            ))
            api_task = asyncio.create_task(api_download_audio(link, vault_path)) if USE_AUDIO_API else None
        else:
            # Video: prefer MP4
            fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            yt_task = asyncio.create_task(run_with_semaphore(
                loop.run_in_executor(None, download_with_ytdlp_sync, link, vault_path, fmt)
            ))
            api_task = asyncio.create_task(api_download_video(link, vault_path)) if USE_VIDEO_API else None

        # Execute Race
        result = await race_ytdlp_and_api(yt_task, api_task, title or link_hash)
        
        # Verify result is at vault_path
        if result and result != vault_path:
             if os.path.exists(result):
                 shutil.move(result, vault_path)
                 return vault_path
        return result if (result and os.path.exists(result)) else None

    # Execute with deduplication
    final_path = await deduplicate_download(key, run_download_logic)
    
    return final_path


# ==============================================================================
# 9. Initialization (Start Cleaner)
# ==============================================================================

# Start the cleaner task automatically if loop is running
try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(buffer_cleaner_loop())
except Exception:
    pass
