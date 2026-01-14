# Authored By Certified Coders © 2026
# Fixed Downloader for AnnieXMedia - Final Fix for Async Future Error & HLS
# Fixes: TypeError (Future vs Coroutine), NoVideoSourceFound, Empty File.

import asyncio
import contextlib
import glob
import os
import re
import shlex
import shutil
import subprocess
import time
import hashlib
import html
from typing import Dict, Optional, List

import aiofiles
import aiohttp
from aiohttp import TCPConnector
from yt_dlp import YoutubeDL

# --- Imports from AnnieXMedia Project Structure ---
from AnnieXMedia.core.dir import CACHE_DIR, DOWNLOAD_DIR
from AnnieXMedia.utils.cookie_handler import COOKIE_PATH as _COOKIES_FILE
from AnnieXMedia.utils.tuning import CHUNK_SIZE, SEM
from config import API_KEY, API_URL, VIDEO_API_URL
from AnnieXMedia.logging import LOGGER
from AnnieXMedia.misc import db as _GLOBAL_DB

LOGGER = LOGGER(__name__)

# --- Configuration ---
USE_AUDIO_API = bool(API_URL and API_KEY)
USE_VIDEO_API = bool(VIDEO_API_URL and API_KEY)
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
ARIA2_PATH = shutil.which("aria2c")

# --- Directories ---
AUDIO_DIR = os.path.join(DOWNLOAD_DIR, "audio")
VIDEO_DIR = os.path.join(DOWNLOAD_DIR, "video")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

# --- State Management ---
_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()
_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()

# Cache Settings
CACHE_TTL = 8 * 60  # 8 Minutes
_cache_registry: Dict[str, float] = {}
_cache_lock = asyncio.Lock()


# ---------------------------------------------------------------------------------
#                                 CACHE MANAGER
# ---------------------------------------------------------------------------------

async def register_cache(path: str) -> None:
    if not path: return
    try:
        async with _cache_lock:
            _cache_registry[path] = time.time() + CACHE_TTL
    except Exception:
        _cache_registry[path] = time.time() + CACHE_TTL

def _register_cache_from_thread(path: str) -> None:
    if not path: return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(asyncio.create_task, register_cache(path))
        else:
            _cache_registry[path] = time.time() + CACHE_TTL
    except Exception:
        pass

def _is_file_in_use(path: str) -> bool:
    try:
        for k, q in list(_GLOBAL_DB.items()):
            if not q: continue
            for item in q:
                if isinstance(item, dict):
                    if item.get("file") == path or item.get("speed_path") == path:
                        return True
    except Exception:
        return True 
    return False

async def _cache_cleaner_loop() -> None:
    LOGGER.info("Cache cleaner loop started.")
    while True:
        try:
            await asyncio.sleep(30)
            now = time.time()
            to_delete = []
            async with _cache_lock:
                for p, expiry in list(_cache_registry.items()):
                    if expiry <= now:
                        if not _is_file_in_use(p) and os.path.exists(p):
                            to_delete.append(p)
                        else:
                            _cache_registry[p] = now + CACHE_TTL
            
            for p in to_delete:
                try:
                    os.remove(p)
                    async with _cache_lock:
                        _cache_registry.pop(p, None)
                    LOGGER.info(f"Cleaned: {os.path.basename(p)}")
                except Exception:
                    pass
        except Exception as e:
            LOGGER.error(f"Cache cleaner error: {e}")

def init_cache_cleaner() -> None:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_cache_cleaner_loop())
    except Exception:
        pass


# ---------------------------------------------------------------------------------
#                                 HELPERS & UTILS
# ---------------------------------------------------------------------------------

def _safe_title_for_filename(title: str) -> str:
    if not title: return str(int(time.time()))
    try:
        s = html.unescape(title)
        s = re.sub(r"[^\w\s-]", "", s)
        s = re.sub(r"\s+", "_", s.strip())
        return s[:40] 
    except:
        return str(int(time.time()))

def extract_video_id(link: str) -> str:
    if not link: return ""
    s = link.strip()
    if YOUTUBE_ID_RE.match(s): return s
    if "v=" in s:
        try: return s.split("v=")[1].split("&")[0]
        except: pass
    if "youtu.be" in s:
        try: return s.split("/")[-1].split("?")[0]
        except: pass
    return ""

def _make_link_id(link: str) -> str:
    if not link: return "unknown"
    return hashlib.sha256(link.encode()).hexdigest()[:12]

def find_cached_file(video_id: str, kind: str) -> Optional[str]:
    if not video_id: return None
    
    target_dir = AUDIO_DIR if kind == "audio" else VIDEO_DIR
    pattern = os.path.join(target_dir, f"{video_id}_{kind}_*.mp4")
    
    matches = glob.glob(pattern)
    if kind == "audio":
        matches += glob.glob(os.path.join(target_dir, f"{video_id}_{kind}_*.m4a"))

    if matches:
        # Verify file size > 0
        valid_matches = [m for m in matches if os.path.getsize(m) > 0]
        if valid_matches:
            best = sorted(valid_matches, key=os.path.getmtime, reverse=True)[0]
            _register_cache_from_thread(best)
            return best
    
    return None


# ---------------------------------------------------------------------------------
#                                 FFMPEG HANDLERS
# ---------------------------------------------------------------------------------

def _run_ffmpeg_convert(input_src: str, out_path: str, kind: str = "video") -> bool:
    try:
        if kind == "video":
            # Force conversion to simple H.264/AAC for Telegram
            cmd = (
                f'ffmpeg -y -hide_banner -loglevel error '
                f'-i {shlex.quote(input_src)} '
                f'-c:v libx264 -preset veryfast -crf 26 '
                f'-pix_fmt yuv420p '
                f'-c:a aac -b:a 128k '
                f'-movflags +faststart '
                f'{shlex.quote(out_path)}'
            )
        else:
            cmd = (
                f'ffmpeg -y -hide_banner -loglevel error '
                f'-i {shlex.quote(input_src)} '
                f'-c:a aac -b:a 128k -vn '
                f'{shlex.quote(out_path)}'
            )

        proc = subprocess.run(cmd, shell=True, timeout=900)
        
        if proc.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
            return True
            
        LOGGER.error(f"FFmpeg conversion failed. Return code: {proc.returncode}")
        return False
    except subprocess.TimeoutExpired:
        LOGGER.error("FFmpeg process timed out")
        return False
    except Exception as e:
        LOGGER.error(f"FFmpeg Exception: {e}")
        return False

def _ensure_named_final(path: str, vid: str, kind: str, title: str) -> Optional[str]:
    """Validates file exists and renames/converts it."""
    if not path or not os.path.exists(path):
        LOGGER.error(f"File not found after download: {path}")
        return None
    
    if os.path.getsize(path) < 100:
        LOGGER.error("Downloaded file is empty or too small.")
        try: os.remove(path)
        except: pass
        return None
    
    out_dir = AUDIO_DIR if kind == "audio" else VIDEO_DIR
    safe_title = _safe_title_for_filename(title)
    ext = "mp4" if kind == "video" else "m4a"
    final_name = os.path.join(out_dir, f"{vid}_{kind}_{safe_title}.{ext}")

    # Check if we need conversion (e.g. m3u8 or raw stream)
    is_manifest = path.endswith(".m3u8") or "manifest" in path
    
    # Always convert if it's a manifest or if names don't match
    if is_manifest or (kind == "video" and not path.endswith(".mp4")):
        LOGGER.info(f"Converting file to Telegram Standard: {path}")
        if _run_ffmpeg_convert(path, final_name, kind):
            try: os.remove(path) 
            except: pass
            _register_cache_from_thread(final_name)
            return final_name
        return None

    # Simple Rename
    if path != final_name:
        try:
            shutil.move(path, final_name)
        except:
            shutil.copy(path, final_name)
            try: os.remove(path)
            except: pass
            
    _register_cache_from_thread(final_name)
    return final_name


# ---------------------------------------------------------------------------------
#                                 YT-DLP WORKER
# ---------------------------------------------------------------------------------

def download_with_ytdlp_sync(link: str, kind: str, title_hint: str) -> Optional[str]:
    """Blocking yt-dlp function."""
    try:
        vid = extract_video_id(link) or _make_link_id(link)
        out_dir = AUDIO_DIR if kind == "audio" else VIDEO_DIR
        outtmpl = os.path.join(out_dir, f"{vid}_temp.%(ext)s")
        
        opts = {
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "ignoreerrors": True,
            "nocheckcertificate": True,
            "geo_bypass": True,
            "retries": 10,
            "socket_timeout": 15,
        }
        
        if _COOKIES_FILE and os.path.exists(_COOKIES_FILE):
            opts["cookiefile"] = _COOKIES_FILE

        # Disable Aria2 for GoogleVideo links to prevent 403s
        is_sensitive = "googlevideo" in link or "m3u8" in link
        if ARIA2_PATH and not is_sensitive:
            opts["external_downloader"] = "aria2c"
            opts["external_downloader_args"] = ["-x", "8", "-k", "1M"]
        
        if kind == "audio":
            opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
        else:
            # Prefer AVC1 (H.264) for Telegram
            opts["format"] = "bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            opts["merge_output_format"] = "mp4"

        with YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(link, download=True)
            except Exception as e:
                LOGGER.error(f"yt-dlp extract failed: {e}")
                return None

            if not info: return None
            
            # Find the actual downloaded file
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                # Fallback search if merger changed extension
                base = os.path.splitext(filename)[0]
                possible = glob.glob(f"{base}*")
                if possible:
                    filename = max(possible, key=os.path.getctime)
            
            return _ensure_named_final(filename, vid, kind, title_hint or info.get("title", ""))

    except Exception as e:
        LOGGER.error(f"Yt-dlp General Error: {e}")
        return None


# ---------------------------------------------------------------------------------
#                                 ASYNC MANAGERS
# ---------------------------------------------------------------------------------

async def get_session():
    global _session
    async with _session_lock:
        if _session is None or _session.closed:
            _session = aiohttp.ClientSession(connector=TCPConnector(limit=0, ttl_dns_cache=300))
    return _session

async def api_download(link: str, kind: str, title: str) -> Optional[str]:
    if kind == "audio" and not USE_AUDIO_API: return None
    if kind == "video" and not USE_VIDEO_API: return None
    
    vid = extract_video_id(link)
    base_url = API_URL if kind == "audio" else VIDEO_API_URL
    endpoint = "song" if kind == "audio" else "video"
    
    try:
        session = await get_session()
        target_url = f"{base_url}/{endpoint}/{vid}?api={API_KEY}"
        
        for _ in range(30):
            async with session.get(target_url) as r:
                if r.status != 200: return None
                data = await r.json()
                status = str(data.get("status", "")).lower()

                if status == "done":
                    dlink = data.get("link")
                    if not dlink: return None
                    
                    safe_title = _safe_title_for_filename(data.get("title", title))
                    ext = "mp4" if kind == "video" else "m4a"
                    temp_path = os.path.join(VIDEO_DIR if kind == "video" else AUDIO_DIR, f"api_{vid}_{int(time.time())}.{ext}")
                    
                    async with session.get(dlink) as f_resp:
                        if f_resp.status == 200:
                            async with aiofiles.open(temp_path, "wb") as f:
                                async for chunk in f_resp.content.iter_chunked(CHUNK_SIZE):
                                    await f.write(chunk)
                    
                    return _ensure_named_final(temp_path, vid, kind, data.get("title", title))
                
                if status == "error":
                    return None
            await asyncio.sleep(1)
    except Exception as e:
        LOGGER.debug(f"API Error: {e}")
    return None

# --- FIXED RACE HANDLER ---
async def race_handler(link: str, kind: str, title: str) -> Optional[str]:
    """Properly handles race between sync (yt-dlp) and async (api)."""
    loop = asyncio.get_event_loop()
    
    # WRAPPER to convert sync function to awaitable coroutine
    async def run_ytdlp():
        return await loop.run_in_executor(None, download_with_ytdlp_sync, link, kind, title)

    # Now we create tasks from coroutines, NOT futures
    t1 = asyncio.create_task(run_ytdlp())
    t2 = asyncio.create_task(api_download(link, kind, title))
    
    tasks = [t1, t2]
    
    # Wait for the first one to complete
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    
    result = None
    for t in done:
        try:
            res = t.result()
            if res and os.path.exists(res) and os.path.getsize(res) > 0:
                result = res
                break
        except Exception as e:
            LOGGER.error(f"Task exception in race: {e}")
            pass
        
    # If first one failed, verify pending
    if not result and pending:
        # Give remaining task a bit more time or cancel
        # Here we just cancel to fail fast, or wait? Let's wait briefly if t2 is API
        for p in pending:
            p.cancel()
    else:
         for p in pending:
            p.cancel()

    return result


# ---------------------------------------------------------------------------------
#                                 PUBLIC INTERFACE
# ---------------------------------------------------------------------------------

async def yt_dlp_download(link: str, type: str = "audio", title: str = "") -> Optional[str]:
    kind = "video" if type == "video" else "audio"
    vid = extract_video_id(link) or _make_link_id(link)
    
    # 1. Check Cache
    if cached := find_cached_file(vid, kind):
        LOGGER.info(f"Cache Hit: {os.path.basename(cached)}")
        return cached

    # 2. In-flight protection
    key = f"{vid}_{kind}"
    async with _inflight_lock:
        if key in _inflight:
            try:
                LOGGER.info(f"Waiting for existing download: {key}")
                return await asyncio.wait_for(_inflight[key], timeout=300)
            except:
                pass 
        
        future = asyncio.get_event_loop().create_future()
        _inflight[key] = future

    try:
        # 3. Start Download Race
        async with SEM: 
            result = await race_handler(link, kind, title)
        
        if result and os.path.exists(result):
            LOGGER.info(f"Download Success: {os.path.basename(result)}")
            if not future.done(): future.set_result(result)
            return result
        else:
            LOGGER.error("Download returned None or file missing.")
            if not future.done(): future.set_result(None)
            return None

    except Exception as e:
        LOGGER.exception(f"Fatal Download Error: {e}")
        if not future.done(): future.set_result(None)
        return None
    finally:
        async with _inflight_lock:
            _inflight.pop(key, None)
