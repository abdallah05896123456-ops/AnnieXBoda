# Authored By Certified Coders © 2026
# 💎 THE TITAN EDITION: Enterprise Grade | Smart Cache | Auto-Heal 💎

import asyncio
import json
import os
import re
import time
import logging
from typing import Dict, List, Optional, Tuple, Union

import aiohttp
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.aio import Playlist, VideosSearch

from AnnieXMedia.utils.cookie_handler import COOKIE_PATH
from AnnieXMedia.utils.database import is_on_off
from AnnieXMedia.utils.downloader import yt_dlp_download
from AnnieXMedia.utils.errors import capture_internal_err
from AnnieXMedia.utils.formatters import time_to_seconds
from AnnieXMedia.utils.tuning import (
    YOUTUBE_META_MAX,
    YOUTUBE_META_TTL,
    YTDLP_TIMEOUT,
)

# === Logger Setup ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnnieMusic.YouTube")

# === Advanced In-Memory Cache ===
# Cache Structure: { "query": (timestamp, data) }
_meta_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_meta_lock = asyncio.Lock()

_fmt_cache: Dict[str, Tuple[float, List[Dict], str]] = {}
_fmt_lock = asyncio.Lock()


# === Constants & Regex ===
YOUTUBE_IMG_URL = "https://te.legra.ph/file/6298d377ad3eb46711644.jpg"
YOUTUBE_REGEX = r"(?:youtube\.com|youtu\.be)"
LIVE_CHECK_CMD = ["--dump-json"]


# === 🍪 INTELLIGENT COOKIE MANAGER ===
class CookieManager:
    @staticmethod
    async def get_cookies_args() -> List[str]:
        """
        Retrieves the best available cookie file path.
        Checks: Environment > Config Path > 'cookies' folder.
        """
        path = str(COOKIE_PATH)
        
        # 1. Check if specific file exists and is valid
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return ["--cookies", path]
            
        # 2. Check for Upstream/Env Cookies
        env_cookie = os.getenv("COOKIE_URL") or os.getenv("UPSTREAM_COOKIES")
        if env_cookie:
            try:
                async with aiohttp.ClientSession() as session:
                    # Fix raw links for common pastebins
                    if "pastebin.com" in env_cookie and "/raw/" not in env_cookie:
                        env_cookie = env_cookie.replace("pastebin.com/", "pastebin.com/raw/")
                    elif "batbin.me" in env_cookie and "/raw/" not in env_cookie:
                        env_cookie = env_cookie.replace("batbin.me/", "batbin.me/raw/")
                        
                    async with session.get(env_cookie) as resp:
                        if resp.status == 200:
                            content = await resp.text()
                            with open(path, "w", encoding="utf-8") as f:
                                f.write(content)
                            return ["--cookies", path]
            except Exception as e:
                logger.error(f"Failed to fetch upstream cookies: {e}")

        # 3. Auto-detect in folder
        try:
            if os.path.exists("cookies"):
                for file in os.listdir("cookies"):
                    if file.endswith(".txt"):
                        return ["--cookies", os.path.join("cookies", file)]
        except:
            pass
            
        return []


# === ⚡ ASYNC PROCESS EXECUTOR ===
async def run_async_cmd(cmd: List[str]) -> Tuple[bytes, bytes]:
    """
    Executes a shell command asynchronously with timeout protection.
    Replaces blocking subprocess.run calls.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            return await asyncio.wait_for(process.communicate(), timeout=YTDLP_TIMEOUT)
        except asyncio.TimeoutError:
            process.kill()
            logger.warning(f"Command timed out: {cmd[0]}")
            return b"", b"Timeout"
    except Exception as e:
        logger.error(f"Process execution failed: {e}")
        return b"", str(e).encode()


# === 🧠 CACHE CONTROLLER ===
async def get_cached_result(query: str) -> Optional[List[Dict]]:
    key = f"search:{query}"
    now = time.time()
    
    async with _meta_lock:
        # Garbage Collection
        if len(_meta_cache) > YOUTUBE_META_MAX:
            keys_to_remove = [k for k, v in _meta_cache.items() if now - v[0] > YOUTUBE_META_TTL]
            for k in keys_to_remove:
                del _meta_cache[k]
            # Hard reset if still full
            if len(_meta_cache) > YOUTUBE_META_MAX:
                _meta_cache.clear()

        # Hit Check
        if key in _meta_cache:
            ts, data = _meta_cache[key]
            if now - ts < YOUTUBE_META_TTL:
                return data
            del _meta_cache[key]
            
    return None

async def set_cached_result(query: str, result: List[Dict]):
    key = f"search:{query}"
    async with _meta_lock:
        _meta_cache[key] = (time.time(), result)


# === 🌟 MAIN API CLASS ===
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = re.compile(YOUTUBE_REGEX)
        # Optimized Args for Speed
        self.base_opts = [
            "--no-warnings",
            "--ignore-errors",
            "--geo-bypass",
            "--nocheckcertificate",
            "--no-playlist",
            "--extractor-args", "youtube:player_client=android", # Faster API
            "--concurrent-fragments", "4", # Multi-threaded download
            "-o", "downloads/%(id)s.%(ext)s"
        ]

    def _clean_url(self, link: str, videoid: Union[str, bool] = None) -> str:
        if videoid and isinstance(videoid, str):
            return f"{self.base}{videoid}"
        
        link = link.strip()
        if "youtu.be" in link:
            return f"{self.base}{link.split('/')[-1].split('?')[0]}"
        if "&" in link:
            return link.split("&")[0]
        return link

    # ==========================
    # 🔍 SEARCH & METADATA
    # ==========================
    @capture_internal_err
    async def get_data(self, query: str, use_cache: bool = True) -> Optional[Dict]:
        """Unified data fetcher with Cache support."""
        query = self._clean_url(query)
        
        # 1. Try Cache
        if use_cache and not query.startswith("http"):
            cached = await get_cached_result(query)
            if cached: return cached[0]

        # 2. Perform Search
        try:
            # Check if it's a direct link to avoid search overhead
            if query.startswith("http"):
                # Use yt-dlp JSON dump for direct links (More accurate)
                cookies = await CookieManager.get_cookies_args()
                cmd = ["yt-dlp", *cookies, "-J", query]
                out, _ = await run_async_cmd(cmd)
                if out:
                    data = json.loads(out)
                    entry = data['entries'][0] if 'entries' in data else data
                    # Normalize to match VideosSearch format
                    return {
                        "id": entry.get("id"),
                        "title": entry.get("title"),
                        "duration": entry.get("duration_string") or str(entry.get("duration")),
                        "thumbnail": entry.get("thumbnail"),
                        "thumbnails": [{"url": entry.get("thumbnail")}],
                        "webpage_url": entry.get("webpage_url"),
                    }

            # Fallback/Default to VideosSearch
            search = await VideosSearch(query, limit=1).next()
            results = search.get("result", [])
            if results:
                if not query.startswith("http"):
                    await set_cached_result(query, results)
                return results[0]
                
        except Exception as e:
            logger.error(f"Search failed for {query}: {e}")
            
        return None

    @capture_internal_err
    async def details(self, link: str, videoid: Union[str, bool] = None):
        data = await self.get_data(self._clean_url(link, videoid))
        if not data:
            raise ValueError("No results found.")
            
        title = data.get("title", "Unknown")
        dur = data.get("duration", "00:00")
        
        # Convert seconds to string if needed
        if isinstance(dur, (int, float)):
            m, s = divmod(int(dur), 60)
            h, m = divmod(m, 60)
            dur = f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
            
        thumb = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL).split("?")[0]
        vidid = data.get("id", "")
        
        return title, dur, time_to_seconds(dur), thumb, vidid

    # === Helper Wrappers for Templates ===
    async def title(self, link, videoid=None):
        d = await self.get_data(self._clean_url(link, videoid))
        return d.get("title", "") if d else ""

    async def duration(self, link, videoid=None):
        d = await self.get_data(self._clean_url(link, videoid))
        return d.get("duration", "00:00") if d else "00:00"

    async def thumbnail(self, link, videoid=None):
        d = await self.get_data(self._clean_url(link, videoid))
        return d.get("thumbnails", [{}])[0].get("url", "") if d else ""

    # ==========================
    # 📥 DOWNLOAD & STREAMING
    # ==========================
    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic,
        video: bool = False,
        videoid: Union[str, bool] = None
    ) -> Tuple[Optional[str], Optional[bool]]:
        
        url = self._clean_url(link, videoid)
        cookies = await CookieManager.get_cookies_args()
        
        # 1. LIVE STREAM CHECK (Fast Path)
        if video:
            cmd = ["yt-dlp", *cookies, "-g", url]
            out, _ = await run_async_cmd(cmd)
            if out:
                stream_link = out.decode().strip().split("\n")[0]
                if ".m3u8" in stream_link:
                    return stream_link, None

        # 2. DEFINING FORMATS STRATEGY (The "Smart" Part)
        # This fixes 'Requested format not available' by cascading down options
        if video:
            format_strategies = [
                # Strategy A: High Quality Merge (Best for quality)
                ("bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best", True),
                # Strategy B: Safe 720p (Best compatibility)
                ("best[height<=720]", True),
                # Strategy C: Raw Fallback (Just make it work)
                ("best", True)
            ]
        else:
            format_strategies = [
                # Strategy A: M4A Direct (Fastest, no conversion)
                ("bestaudio[ext=m4a]", False),
                # Strategy B: Any Audio
                ("bestaudio", False)
            ]

        # 3. EXECUTE DOWNLOAD LOOP
        for fmt, merge_flag in format_strategies:
            try:
                # Construct Command
                cmd = ["yt-dlp", *cookies, *self.base_opts, "-f", fmt, url]
                
                # Force Merge if strategy requires it (Fixes split AV issues)
                if merge_flag:
                    cmd.extend(["--merge-output-format", "mp4"])

                # Run Download
                await run_async_cmd(cmd)

                # 4. FILE VERIFICATION
                # We need to find what file was actually downloaded
                # Using --get-filename is reliable but adds overhead, 
                # so we check standard paths first.
                
                # Extract ID
                vid_id = None
                if "v=" in url:
                    vid_id = url.split("v=")[-1].split("&")[0]
                else:
                    # Get ID via CLI if not in URL
                    id_cmd = ["yt-dlp", "--get-id", url]
                    id_out, _ = await run_async_cmd(id_cmd)
                    if id_out: vid_id = id_out.decode().strip()

                if vid_id:
                    possible_exts = ["mp4", "m4a", "webm", "mkv", "mp3"]
                    for ext in possible_exts:
                        fpath = f"downloads/{vid_id}.{ext}"
                        if os.path.exists(fpath) and os.path.getsize(fpath) > 1024: # > 1KB
                            return fpath, True

            except Exception as e:
                logger.warning(f"Download strategy {fmt} failed: {e}")
                continue

        # 5. LAST RESORT (Internal Downloader)
        # If everything fails, try the older pytube-based or generic fallback
        if await is_on_off(1):
             try:
                 title = await self.title(url)
                 path = await yt_dlp_download(url, type="video" if video else "audio", title=title)
                 if path: return path, True
             except:
                 pass

        return None, None

    # ==========================
    # 📜 UTILITIES
    # ==========================
    @capture_internal_err
    async def playlist(self, link, limit, user_id, videoid=None):
        url = self._clean_url(link, videoid)
        if "playlist" not in url:
            url = f"https://youtube.com/playlist?list={videoid}" if videoid else url

        # 1. Try python-lib first (Faster for metadata)
        try:
            pl = await Playlist.get(url)
            ids = [v['id'] for v in pl.get('videos', [])[:limit] if v.get('id')]
            if ids: return ids
        except:
            pass

        # 2. Fallback to CLI (More robust)
        cookies = await CookieManager.get_cookies_args()
        cmd = [
            "yt-dlp", *cookies, 
            "-i", "--flat-playlist", "--get-id", 
            "--playlist-end", str(limit), 
            url
        ]
        out, _ = await run_async_cmd(cmd)
        if out:
            return out.decode().strip().split("\n")
        return []

    @capture_internal_err
    async def track(self, link, videoid=None):
        data = await self.get_data(self._clean_url(link, videoid))
        if not data:
             # Deep Fetch if simple fetch fails
             url = self._clean_url(link, videoid)
             cookies = await CookieManager.get_cookies_args()
             out, _ = await run_async_cmd(["yt-dlp", *cookies, "-J", url])
             if out:
                 data = json.loads(out)
             else:
                 return {}, ""

        thumb = data.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
        return {
            "title": data.get("title", "Unknown"),
            "link": data.get("webpage_url", link),
            "vidid": data.get("id"),
            "duration_min": data.get("duration", "00:00"),
            "thumb": thumb
        }, data.get("id")

    @capture_internal_err
    async def formats(self, link, videoid=None):
        url = self._clean_url(link, videoid)
        cookies = await CookieManager.get_cookies_args()
        
        # Check Format Cache
        key = f"fmt:{url}"
        async with _fmt_lock:
             if key in _fmt_cache:
                 if time.time() - _fmt_cache[key][0] < YOUTUBE_META_TTL:
                     return _fmt_cache[key][1], url

        # Fetch Formats
        cmd = ["yt-dlp", *cookies, "-J", url]
        out, _ = await run_async_cmd(cmd)
        
        valid_formats = []
        if out:
            data = json.loads(out)
            for f in data.get("formats", []):
                # Filter usable formats
                if "dash" in str(f.get("format")).lower(): continue
                valid_formats.append({
                    "format": f.get("format"),
                    "filesize": f.get("filesize") or f.get("filesize_approx", 0),
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution"),
                    "yturl": url
                })
        
        # Update Cache
        async with _fmt_lock:
            _fmt_cache[key] = (time.time(), valid_formats, url)
            
        return valid_formats, url

    @capture_internal_err
    async def slider(self, link, query_type, videoid=None):
        url = self._clean_url(link, videoid)
        # Use VideosSearch for list functionality
        search = await VideosSearch(url, limit=15).next()
        results = search.get("result", [])
        
        if query_type >= len(results):
             return None, None, None, None
             
        item = results[query_type]
        return (
            item.get("title"),
            item.get("duration"),
            item.get("thumbnails", [{}])[0].get("url").split("?")[0],
            item.get("id")
        )

    @capture_internal_err
    async def video(self, link, videoid=None):
        """Get Direct Stream Link (For live streams or quick play)"""
        url = self._clean_url(link, videoid)
        cookies = await CookieManager.get_cookies_args()
        
        cmd = ["yt-dlp", *cookies, "-g", "-f", "best[height<=720]", url]
        out, err = await run_async_cmd(cmd)
        
        if out:
            return 1, out.decode().split("\n")[0]
        return 0, str(err)

    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        """Extract URL from Message entities."""
        if not message: return None
        
        # Check Reply
        msgs = [message]
        if message.reply_to_message:
            msgs.append(message.reply_to_message)
            
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = msg.entities or msg.caption_entities or []
            
            for entity in entities:
                if entity.type == MessageEntityType.URL:
                    return text[entity.offset:entity.offset+entity.length].split("&")[0]
                if entity.type == MessageEntityType.TEXT_LINK:
                    return entity.url.split("&")[0]
        return None

    @capture_internal_err
    async def exists(self, link: str, videoid=None) -> bool:
        url = self._clean_url(link, videoid)
        return bool(re.search(self.regex, url))
