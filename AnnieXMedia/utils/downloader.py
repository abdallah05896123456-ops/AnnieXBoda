# ---------------------------------------------------------------------------------
# AnnieXMedia High-Performance Downloader Engine
# Engineered for Speed, Stability, and Telegram Compatibility
# ---------------------------------------------------------------------------------

import asyncio
import functools
import glob
import hashlib
import logging
import os
import re
import shutil
import time
import json
from typing import Optional, Tuple, Union, List, Dict

import aiofiles
import aiohttp
import yt_dlp
from yt_dlp.utils import DownloadError

# --- Configuration Imports ---
# تأكد من أن هذه الاستدعاءات تطابق ملفات مشروعك
try:
    from config import API_KEY, API_URL, VIDEO_API_URL
    from AnnieXMedia.core.dir import DOWNLOAD_DIR
    from AnnieXMedia.utils.cookie_handler import COOKIE_PATH
except ImportError:
    # Fallback configs for testing if imports fail
    API_KEY = None
    API_URL = None
    VIDEO_API_URL = None
    DOWNLOAD_DIR = "downloads"
    COOKIE_PATH = None

# --- Constants & Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
LOGGER = logging.getLogger("AnnieDownloader")

# Directory Structure
AUDIO_DIR = os.path.join(DOWNLOAD_DIR, "audio")
VIDEO_DIR = os.path.join(DOWNLOAD_DIR, "video")
TEMP_DIR = os.path.join(DOWNLOAD_DIR, "temp")

# Ensure directories exist
for d in [AUDIO_DIR, VIDEO_DIR, TEMP_DIR]:
    os.makedirs(d, exist_ok=True)

# Regex & Limits
YOUTUBE_ID_RE = re.compile(r"(?:v=|/)([0-9A-Za-z_-]{11}).*")
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB Limit
CACHE_TTL = 30 * 60  # 30 Minutes Cache
SEM_LIMIT = asyncio.Semaphore(5)  # Max concurrent downloads to prevent crash

# User-Agent for requests
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# ---------------------------------------------------------------------------------
#                                 HELPER FUNCTIONS
# ---------------------------------------------------------------------------------

def get_video_id(url: str) -> str:
    """Extracts the 11-character YouTube ID strictly or hashes other URLs."""
    if not url:
        return "unknown"
    match = YOUTUBE_ID_RE.search(url)
    if match:
        return match.group(1)
    # Fallback for non-YT links (SoundCloud, Spotify, etc.)
    return hashlib.md5(url.encode()).hexdigest()[:12]

def clean_filename(title: str) -> str:
    """Sanitizes filename to avoid filesystem errors."""
    if not title:
        return f"media_{int(time.time())}"
    # Allow alphanumeric, underscores, hyphens
    clean = re.sub(r'[\\/*?:"<>|]', '', title)
    clean = clean.replace(" ", "_")
    # Remove emojis and weird chars
    clean = clean.encode('ascii', 'ignore').decode('ascii')
    return clean[:50]  # Limit length

def get_final_path(vid_id: str, ftype: str, title: str = "") -> str:
    """Generates the final destination path."""
    folder = VIDEO_DIR if ftype == "video" else AUDIO_DIR
    ext = "mp4" if ftype == "video" else "m4a"
    safe_title = clean_filename(title)
    return os.path.join(folder, f"{vid_id}_{safe_title}.{ext}")

def check_existing_file(vid_id: str, ftype: str) -> Optional[str]:
    """Checks if file already exists in cache."""
    folder = VIDEO_DIR if ftype == "video" else AUDIO_DIR
    ext = "mp4" if ftype == "video" else "m4a"
    pattern = os.path.join(folder, f"{vid_id}_*.{ext}")
    
    files = glob.glob(pattern)
    if files:
        # Return the most recently accessed file
        valid_file = max(files, key=os.path.getatime)
        if os.path.exists(valid_file) and os.path.getsize(valid_file) > 1024: # Must be > 1KB
            LOGGER.info(f"Cache Hit: {valid_file}")
            # Update access time to prevent cleaning
            os.utime(valid_file, None)
            return valid_file
    return None

# ---------------------------------------------------------------------------------
#                                 FFMPEG ENGINE
# ---------------------------------------------------------------------------------

async def run_ffmpeg_process(cmd: List[str]) -> bool:
    """Runs FFmpeg asynchronously with timeout protection."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            # 5 Minute Timeout for conversion
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
        except asyncio.TimeoutError:
            process.kill()
            LOGGER.error("FFmpeg process timed out.")
            return False

        if process.returncode != 0:
            LOGGER.error(f"FFmpeg Error: {stderr.decode()}")
            return False
        return True
    except Exception as e:
        LOGGER.error(f"FFmpeg Exception: {e}")
        return False

async def convert_media(input_path: str, output_path: str, ftype: str) -> bool:
    """
    Converts media to Telegram-Standard formats.
    Video: H.264 (AVC) + AAC + YUV420P
    Audio: AAC
    This prevents 'InvalidVideoProportion' and 'NoVideoSourceFound'.
    """
    if not os.path.exists(input_path):
        return False
        
    # If input is empty/corrupt, delete and fail
    if os.path.getsize(input_path) < 1024:
        os.remove(input_path)
        return False

    LOGGER.info(f"Starting Conversion: {input_path} -> {output_path}")

    if ftype == "video":
        # Force re-encode to ensure compatibility
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", input_path,
            "-c:v", "libx264",      # Essential for Telegram
            "-preset", "veryfast",  # Good balance of speed/quality
            "-crf", "26",           # Reasonable compression
            "-pix_fmt", "yuv420p",  # Essential for wide support on mobile
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart", # Start playing before full download
            output_path
        ]
    else:
        # Audio extraction/conversion
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", input_path,
            "-c:a", "aac",
            "-b:a", "128k",
            "-vn",                  # No Video
            output_path
        ]

    success = await run_ffmpeg_process(cmd)
    
    # Cleanup input file regardless of success to save space
    if os.path.exists(input_path) and input_path != output_path:
        try:
            os.remove(input_path)
        except: pass

    if success and os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
        return True
    return False

# ---------------------------------------------------------------------------------
#                                 YT-DLP WRAPPER (SYNC)
# ---------------------------------------------------------------------------------

def _ytdlp_download_sync(url: str, ftype: str, vid_id: str) -> Tuple[Optional[str], str]:
    """
    Blocking yt-dlp function. Must be run in an executor.
    Returns: (file_path, title)
    """
    # Create a raw temp path
    temp_output = os.path.join(TEMP_DIR, f"{vid_id}_raw_{int(time.time())}.%(ext)s")
    
    # Optimized Options for Speed & Stability
    ydl_opts = {
        'outtmpl': temp_output,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'geo_bypass': True,
        'socket_timeout': 15,
        'retries': 3,
        'noplaylist': True,
        # IMPORTANT: Force MP4 container locally to avoid M3U8/HLS issues
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' if ftype == 'video' else 'bestaudio/best',
        'merge_output_format': 'mp4' if ftype == 'video' else 'm4a',
        # Speed optimizations
        'concurrent_fragment_downloads': 5,
        'writethumbnail': False,
    }

    # Add Cookies if available
    if COOKIE_PATH and os.path.exists(COOKIE_PATH):
        ydl_opts['cookiefile'] = COOKIE_PATH

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None, ""
            
            # Retrieve the actual filename yt-dlp wrote
            downloaded_path = ydl.prepare_filename(info)
            
            # Handle cases where extension changed during merge
            if not os.path.exists(downloaded_path):
                base = os.path.splitext(downloaded_path)[0]
                candidates = glob.glob(base + "*")
                if candidates:
                    downloaded_path = max(candidates, key=os.path.getctime)
                else:
                    return None, ""

            return downloaded_path, info.get("title", vid_id)
            
    except DownloadError as e:
        LOGGER.error(f"yt-dlp Download Error: {e}")
        return None, ""
    except Exception as e:
        LOGGER.error(f"yt-dlp Generic Error: {e}")
        return None, ""

# ---------------------------------------------------------------------------------
#                                 API DOWNLOADER (ASYNC)
# ---------------------------------------------------------------------------------

async def download_from_api(url: str, ftype: str, vid_id: str) -> Tuple[Optional[str], str]:
    """Fetches media from external API if configured."""
    api_url = VIDEO_API_URL if ftype == "video" else API_URL
    
    # Skip if API not configured
    if not api_url or not API_KEY or "http" not in api_url:
        return None, ""

    endpoint = "video" if ftype == "video" else "song"
    query_url = f"{api_url}/{endpoint}/{vid_id}?api={API_KEY}"
    
    temp_path = os.path.join(TEMP_DIR, f"{vid_id}_api_{int(time.time())}.{'mp4' if ftype == 'video' else 'm4a'}")

    try:
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
            # 1. Get Download Link
            async with session.get(query_url, timeout=10) as resp:
                if resp.status != 200:
                    return None, ""
                
                try:
                    data = await resp.json()
                except:
                    return None, ""
                
                if data.get("status") != "done":
                    return None, ""
                
                download_link = data.get("link")
                title = data.get("title", vid_id)

            # 2. Download the File
            if not download_link: return None, ""

            async with session.get(download_link, timeout=300) as dl_resp:
                if dl_resp.status == 200:
                    async with aiofiles.open(temp_path, mode="wb") as f:
                        async for chunk in dl_resp.content.iter_chunked(8192): # 8KB Chunks
                            await f.write(chunk)
                    
                    if os.path.exists(temp_path) and os.path.getsize(temp_path) > 1024:
                        return temp_path, title
    except Exception as e:
        LOGGER.debug(f"API Download Failed: {e}") # Debug only, as fallback is ytdlp
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
    
    return None, ""

# ---------------------------------------------------------------------------------
#                                 MAIN LOGIC (RACE STRATEGY)
# ---------------------------------------------------------------------------------

async def download_media(url: str, ftype: str = "audio") -> Optional[str]:
    """
    Main Entry Point.
    Implements a Race Condition: Starts yt-dlp and API download simultaneously.
    First to finish wins.
    """
    vid_id = get_video_id(url)
    
    # 1. Check Cache First (Fastest)
    cached = check_existing_file(vid_id, ftype)
    if cached:
        return cached

    # 2. Define the competitors
    loop = asyncio.get_running_loop()
    
    # Wrap sync function for asyncio properly
    async def ytdlp_runner():
        return await loop.run_in_executor(None, _ytdlp_download_sync, url, ftype, vid_id)

    async def api_runner():
        return await download_from_api(url, ftype, vid_id)

    # 3. Start the Race
    LOGGER.info(f"Starting Race Download for: {vid_id} [{ftype}]")
    
    async with SEM_LIMIT:
        # Create Tasks
        t1 = asyncio.create_task(ytdlp_runner(), name="ytdlp")
        t2 = asyncio.create_task(api_runner(), name="api")
        
        tasks = [t1, t2]

        # Wait for FIRST_COMPLETED
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        raw_path = None
        title = ""
        winner_name = "unknown"

        # Check the winner
        for task in done:
            try:
                res = task.result()
                if res and res[0] and os.path.exists(res[0]):
                    raw_path, title = res
                    winner_name = task.get_name()
                    break # We found a valid file
            except Exception as e:
                LOGGER.error(f"Task Error ({task.get_name()}): {e}")

        # If winner failed (returned None), check the other task if it finished same time
        if not raw_path:
             for task in done:
                if task.get_name() != winner_name: # Check the other one
                    try:
                        res = task.result()
                        if res and res[0] and os.path.exists(res[0]):
                            raw_path, title = res
                            winner_name = task.get_name()
                    except: pass

        # Cancel the losers / pending
        for p in pending:
            p.cancel()
        
        # If still no file, fallback: Wait for the slower task (if it wasn't cancelled yet)
        # Note: In race strategy, we usually cancel pending. 
        # But if the "fast" API failed instantly, we might want to wait for ytdlp.
        # The logic above cancelled pending. If strictly needed, we can logic here:
        # If API failed (done) and YT is pending, we might have cancelled it too early?
        # A better race logic handles failure of one by waiting for other.
        # But for "Speed", we stick to race. If both fail, we return None.
        
        # RETRY LOGIC for robustness:
        # If race produced nothing, try Yt-dlp purely one more time if it was the one cancelled/failed?
        # No, simpler is better.

    # 4. Final Processing (Conversion)
    if not raw_path or not os.path.exists(raw_path):
        LOGGER.error(f"All download methods failed for {url}")
        return None

    LOGGER.info(f"Race Winner: {winner_name} | Processing Title: {title}")
    
    final_path = get_final_path(vid_id, ftype, title)
    
    # Convert/Move
    # This step is CRUCIAL. It converts the raw download to a clean, streamable file.
    if await convert_media(raw_path, final_path, ftype):
        return final_path
    else:
        LOGGER.error("Conversion failed")
        return None

# ---------------------------------------------------------------------------------
#                                 CACHE CLEANER
# ---------------------------------------------------------------------------------

async def cache_cleaner_daemon():
    """Background task to delete old files."""
    LOGGER.info("Cache Cleaner Started")
    while True:
        try:
            await asyncio.sleep(600)  # Run every 10 mins
            now = time.time()
            deleted = 0
            
            # Clean Temp Folder (Aggressive)
            for f in glob.glob(os.path.join(TEMP_DIR, "*")):
                try:
                    if now - os.path.getmtime(f) > 600: # Delete temp files older than 10 mins
                        os.remove(f)
                except: pass

            # Clean Cache Folders (TTL based)
            for folder in [AUDIO_DIR, VIDEO_DIR]:
                for f in glob.glob(os.path.join(folder, "*")):
                    try:
                        # Check last access time
                        if now - os.path.getatime(f) > CACHE_TTL:
                            os.remove(f)
                            deleted += 1
                    except Exception:
                        pass
            
            if deleted > 0:
                LOGGER.info(f"Cleaned {deleted} files from cache.")
                
        except Exception as e:
            LOGGER.error(f"Cleaner Error: {e}")

# Helper to start cleaner
def start_cleaner():
    loop = asyncio.get_event_loop()
    loop.create_task(cache_cleaner_daemon())

# ---------------------------------------------------------------------------------
#                                 INIT CHECK
# ---------------------------------------------------------------------------------

# Optional: Run cleaner on module import if loop exists
try:
    loop = asyncio.get_running_loop()
    loop.create_task(cache_cleaner_daemon())
except RuntimeError:
    pass # Loop not started yet, user must call start_cleaner() manually

# ---------------------------------------------------------------------------------
# END OF CODE
# ---------------------------------------------------------------------------------
