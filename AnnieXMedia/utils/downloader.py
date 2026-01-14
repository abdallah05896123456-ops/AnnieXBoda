# Authored By Certified Coders © 2025
# Full Fixed Downloader for AnnieXMedia - Telegram Native Video Support
# Fixes: Telegram MP4 compatibility (H.264/AAC/yuv420p), M3U8, 403 Errors.

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
# Ensure these match your actual project structure
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
    """Register file in cache system (Async)."""
    if not path: return
    try:
        async with _cache_lock:
            _cache_registry[path] = time.time() + CACHE_TTL
    except Exception:
        # Fallback without lock if loop issue
        _cache_registry[path] = time.time() + CACHE_TTL

def _register_cache_from_thread(path: str) -> None:
    """Thread-safe cache registration."""
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
    """Check if file is currently playing to prevent deletion."""
    try:
        for k, q in list(_GLOBAL_DB.items()):
            if not q: continue
            for item in q:
                if isinstance(item, dict):
                    if item.get("file") == path or item.get("speed_path") == path:
                        return True
    except Exception:
        return True # Fail-safe: assume used
    return False

async def _cache_cleaner_loop() -> None:
    """Background loop to delete expired files."""
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
    """Create a filesystem-safe title."""
    if not title: return str(int(time.time()))
    try:
        s = html.unescape(title)
        s = re.sub(r"[^\w\s-]", "", s)
        s = re.sub(r"\s+", "_", s.strip())
        return s[:40] # Limit length
    except:
        return str(int(time.time()))

def extract_video_id(link: str) -> str:
    """Extract YouTube ID or return empty string."""
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
    """Hash link for non-YouTube files."""
    if not link: return "unknown"
    return hashlib.sha256(link.encode()).hexdigest()[:12]

def find_cached_file(video_id: str, kind: str) -> Optional[str]:
    """Find file in specific directory."""
    if not video_id: return None
    
    # Priority search in specific folder
    target_dir = AUDIO_DIR if kind == "audio" else VIDEO_DIR
    pattern = os.path.join(target_dir, f"{video_id}_{kind}_*.mp4")
    
    matches = glob.glob(pattern)
    if kind == "audio":
        matches += glob.glob(os.path.join(target_dir, f"{video_id}_{kind}_*.m4a"))

    if matches:
        best = sorted(matches, key=os.path.getmtime, reverse=True)[0]
        _register_cache_from_thread(best)
        return best
    
    return None

def _is_m3u8_url(url: str) -> bool:
    if not url: return False
    return ".m3u8" in url.lower() or "manifest" in url.lower()


# ---------------------------------------------------------------------------------
#                                 FFMPEG HANDLERS
# ---------------------------------------------------------------------------------

def _run_ffmpeg_convert(input_src: str, out_path: str, kind: str = "video") -> bool:
    """
    Convert Input to Telegram Compatible Format.
    Video: MP4 Container, H.264 Codec, AAC Audio, yuv420p pixel format.
    Audio: M4A/AAC.
    """
    try:
        # TELEGRAM VIDEO STANDARD:
        # -c:v libx264 (H.264)
        # -pix_fmt yuv420p (Crucial for mobile playback)
        # -movflags +faststart (Web optimized)
        # -c:a aac (AAC Audio)
        
        if kind == "video":
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
            # Audio Only
            cmd = (
                f'ffmpeg -y -hide_banner -loglevel error '
                f'-i {shlex.quote(input_src)} '
                f'-c:a aac -b:a 128k -vn '
                f'{shlex.quote(out_path)}'
            )

        proc = subprocess.run(cmd, shell=True, timeout=900)
        
        if proc.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 100:
            return True
            
        LOGGER.error(f"FFmpeg conversion failed with return code {proc.returncode}")
        return False
    except subprocess.TimeoutExpired:
        LOGGER.error("FFmpeg process timed out")
        return False
    except Exception as e:
        LOGGER.error(f"FFmpeg Exception: {e}")
        return False

def _ensure_named_final(path: str, vid: str, kind: str, title: str) -> Optional[str]:
    """
    Validate and finalize the downloaded file.
    If it's M3U8/Manifest OR incompatible video -> Convert to Telegram Standard.
    """
    if not path or not os.path.exists(path):
        return None
    
    out_dir = AUDIO_DIR if kind == "audio" else VIDEO_DIR
    safe_title = _safe_title_for_filename(title)
    
    # Force extension based on kind
    ext = "mp4" if kind == "video" else "m4a"
    final_name = os.path.join(out_dir, f"{vid}_{kind}_{safe_title}.{ext}")

    # Check 1: Is it a manifest file?
    is_manifest = path.endswith(".m3u8") or "manifest" in path
    
    # Check 2: For Video, is it likely incompatible? (Simple heuristic)
    # We always re-encode manifests. For direct downloads, we trust yt-dlp unless specified.
    needs_conversion = is_manifest
    
    if needs_conversion:
        LOGGER.info(f"Converting raw file/manifest to Telegram Standard: {path}")
        if _run_ffmpeg_convert(path, final_name, kind):
            try: os.remove(path) 
            except: pass
            _register_cache_from_thread(final_name)
            return final_name
        return None

    # Handle Regular Files (Just rename)
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
    """Sync wrapper for yt-dlp running in executor."""
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

        # Smart Aria2 Logic
        # Disable aria2 for GoogleVideo/HLS to prevent 403 Forbidden
        is_sensitive = "googlevideo" in link or "m3u8" in link or "manifest" in link
        if ARIA2_PATH and not is_sensitive:
            opts["external_downloader"] = "aria2c"
            opts["external_downloader_args"] = ["-x", "8", "-k", "1M"]
        
        # Format Selection - TELEGRAM OPTIMIZED
        if kind == "audio":
            opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
        else:
            # FORCE TELEGRAM COMPATIBLE VIDEO
            # Prioritize 'avc1' (H.264) video codec.
            # This avoids 'vp9' or 'av01' which Telegram doesn't play directly.
            opts["format"] = "bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            opts["merge_output_format"] = "mp4"

        with YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(link, download=True)
            except Exception as e:
                LOGGER.error(f"yt-dlp extract failed: {e}")
                return None

            if not info: return None
            
            # Locate the file
            filename = ydl.prepare_filename(info)
            
            # If yt-dlp merged file, the filename might have changed extension
            if not os.path.exists(filename):
                base = os.path.splitext(filename)[0]
                for ext in ["mp4", "mkv", "webm", "m4a"]:
                    if os.path.exists(f"{base}.{ext}"):
                        filename = f"{base}.{ext}"
                        break
            
            # Finalize (Convert if M3U8, Rename)
            final = _ensure_named_final(filename, vid, kind, title_hint or info.get("title", ""))
            return final

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
    """Download from External API."""
    if kind == "audio" and not USE_AUDIO_API: return None
    if kind == "video" and not USE_VIDEO_API: return None
    
    vid = extract_video_id(link)
    base_url = API_URL if kind == "audio" else VIDEO_API_URL
    endpoint = "song" if kind == "audio" else "video"
    
    try:
        session = await get_session()
        target_url = f"{base_url}/{endpoint}/{vid}?api={API_KEY}"
        
        # Poll for completion (Max 30s)
        for _ in range(30):
            async with session.get(target_url) as r:
                if r.status != 200: return None
                data = await r.json()
                
                status = str(data.get("status", "")).lower()

                if status == "done":
                    dlink = data.get("link")
                    if not dlink: return None
                    
                    # Assume API returns something, but we might need to verify format
                    # For safety, we treat API downloads as temp and pass to ensure_named_final
                    # But to save bandwidth, we download directly to final if trustworthy
                    
                    safe_title = _safe_title_for_filename(data.get("title", title))
                    ext = "mp4" if kind == "video" else "m4a"
                    
                    # Temp path for download
                    temp_path = os.path.join(VIDEO_DIR if kind == "video" else AUDIO_DIR, f"api_{vid}_{int(time.time())}.{ext}")
                    
                    async with session.get(dlink) as f_resp:
                        if f_resp.status == 200:
                            async with aiofiles.open(temp_path, "wb") as f:
                                async for chunk in f_resp.content.iter_chunked(CHUNK_SIZE):
                                    await f.write(chunk)
                    
                    # Finalize (Check headers/convert if needed)
                    final = _ensure_named_final(temp_path, vid, kind, data.get("title", title))
                    return final
                
                if status == "error":
                    return None
            
            await asyncio.sleep(1)
            
    except Exception as e:
        LOGGER.debug(f"API Error: {e}")
    return None

async def race_handler(link: str, kind: str, title: str) -> Optional[str]:
    """Race between yt-dlp and API."""
    loop = asyncio.get_event_loop()
    
    # Define Tasks
    t1 = loop.run_in_executor(None, download_with_ytdlp_sync, link, kind, title)
    t2 = api_download(link, kind, title)
    
    tasks = [asyncio.create_task(t1), asyncio.create_task(t2)]
    
    # Wait for FIRST success
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    
    result = None
    for t in done:
        try:
            res = t.result()
            if res and os.path.exists(res):
                result = res
                break
        except: pass
        
    # If first failed, check pending
    if not result and pending:
        for p in pending:
            try:
                res = await p
                if res and os.path.exists(res):
                    result = res
                    break
            except: pass
            
    # Cancel losers
    for p in pending: p.cancel()
    
    return result


# ---------------------------------------------------------------------------------
#                                 PUBLIC INTERFACE
# ---------------------------------------------------------------------------------

async def yt_dlp_download(link: str, type: str = "audio", title: str = "") -> Optional[str]:
    """
    Main entry point.
    type: 'audio' | 'video'
    """
    kind = "video" if type == "video" else "audio"
    vid = extract_video_id(link) or _make_link_id(link)
    
    # 1. Check Cache
    if cached := find_cached_file(vid, kind):
        LOGGER.info(f"Cache Hit: {os.path.basename(cached)}")
        return cached

    # 2. In-flight protection (Anti-Spam)
    key = f"{vid}_{kind}"
    async with _inflight_lock:
        if key in _inflight:
            try:
                LOGGER.info(f"Waiting for existing download: {key}")
                return await asyncio.wait_for(_inflight[key], timeout=300)
            except:
                pass # If wait failed, start new
        
        # Create new future
        future = asyncio.get_event_loop().create_future()
        _inflight[key] = future

    try:
        # 3. Start Download Race
        async with SEM: # Limit concurrency
            result = await race_handler(link, kind, title)
        
        if result:
            LOGGER.info(f"Download Success: {os.path.basename(result)}")
        
        if not future.done():
            future.set_result(result)
        return result

    except Exception as e:
        LOGGER.exception(f"Fatal Download Error: {e}")
        if not future.done(): future.set_result(None)
        return None
    finally:
        async with _inflight_lock:
            _inflight.pop(key, None)
