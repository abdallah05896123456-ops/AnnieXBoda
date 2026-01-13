# Authored By Certified Coders © 2026
# 💎 THE TITAN EDITION: NATIVE API + CLI HYBRID | ANTI-CRASH 💎

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
logging.getLogger("yt_dlp").setLevel(logging.ERROR)
logger = logging.getLogger("AnnieMusic.YouTube")

# === Advanced In-Memory Cache ===
_meta_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_meta_lock = asyncio.Lock()
_fmt_cache: Dict[str, Tuple[float, List[Dict], str]] = {}
_fmt_lock = asyncio.Lock()


# === Constants & Regex ===
YOUTUBE_IMG_URL = "https://te.legra.ph/file/6298d377ad3eb46711644.jpg"
YOUTUBE_REGEX = r"(?:youtube\.com|youtu\.be)"


# === 🍪 INTELLIGENT COOKIE MANAGER ===
class CookieManager:
    @staticmethod
    def get_cookie_file() -> Optional[str]:
        """Returns the path to a valid cookie file if it exists."""
        path = str(COOKIE_PATH)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
            
        # Directory Scan
        try:
            if os.path.exists("cookies"):
                for file in os.listdir("cookies"):
                    if file.endswith(".txt"):
                        return os.path.join("cookies", file)
        except:
            pass
        return None

    @staticmethod
    async def update_cookies():
        """Fetches cookies from Env URL and saves them."""
        env_cookie = os.getenv("COOKIE_URL") or os.getenv("UPSTREAM_COOKIES")
        if env_cookie:
            try:
                if "pastebin.com" in env_cookie and "/raw/" not in env_cookie:
                    env_cookie = env_cookie.replace("pastebin.com/", "pastebin.com/raw/")
                elif "batbin.me" in env_cookie and "/raw/" not in env_cookie:
                    env_cookie = env_cookie.replace("batbin.me/", "batbin.me/raw/")
                        
                async with aiohttp.ClientSession() as session:
                    async with session.get(env_cookie) as resp:
                        if resp.status == 200:
                            content = await resp.text()
                            with open(COOKIE_PATH, "w", encoding="utf-8") as f:
                                f.write(content)
            except Exception as e:
                logger.error(f"Cookie Fetch Error: {e}")


# === ⚡ ASYNC PROCESS EXECUTOR (CLI) ===
async def run_async_cmd(cmd: List[str]) -> Tuple[bytes, bytes]:
    """Executes shell commands safely."""
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
            return b"", b"Timeout"
    except Exception:
        return b"", b"Error"


# === 🌟 MAIN API CLASS ===
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = re.compile(YOUTUBE_REGEX)

    def _clean_url(self, link: str, videoid: Union[str, bool] = None) -> str:
        if videoid and isinstance(videoid, str):
            return f"{self.base}{videoid}"
        link = link.strip()
        if "youtu.be" in link:
            return f"{self.base}{link.split('/')[-1].split('?')[0]}"
        return link.split("&")[0]

    # ==========================
    # 🔍 METADATA (Hybrid: VideosSearch + yt-dlp)
    # ==========================
    @capture_internal_err
    async def get_data(self, query: str, use_cache: bool = True) -> Optional[Dict]:
        query = self._clean_url(query)
        
        # 1. Cache Check
        if use_cache and not query.startswith("http"):
            async with _meta_lock:
                if query in _meta_cache:
                    ts, data = _meta_cache[query]
                    if time.time() - ts < YOUTUBE_META_TTL:
                        return data[0]

        try:
            # 2. Direct Link Handling (Native API)
            if query.startswith("http"):
                cookie = CookieManager.get_cookie_file()
                def _extract():
                    opts = {'quiet': True, 'cookiefile': cookie, 'noplaylist': True}
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        return ydl.extract_info(query, download=False)
                
                data = await asyncio.to_thread(_extract)
                if data:
                    return {
                        "id": data.get("id"),
                        "title": data.get("title"),
                        "duration": data.get("duration"),
                        "thumbnail": data.get("thumbnail"),
                        "webpage_url": data.get("webpage_url"),
                    }
            
            # 3. Search Query Handling (VideosSearch)
            search = await VideosSearch(query, limit=1).next()
            results = search.get("result", [])
            if results:
                async with _meta_lock:
                    _meta_cache[query] = (time.time(), results)
                return results[0]

        except Exception as e:
            logger.error(f"Metadata Error: {e}")
        return None

    @capture_internal_err
    async def details(self, link: str, videoid: Union[str, bool] = None):
        data = await self.get_data(self._clean_url(link, videoid))
        if not data:
            # Fallback try
            try:
                search = await VideosSearch(link, limit=1).next()
                data = search.get("result", [])[0]
            except:
                raise ValueError("No results found.")
            
        title = data.get("title", "Unknown")
        dur = data.get("duration", 0)
        
        if isinstance(dur, (int, float)):
            m, s = divmod(int(dur), 60)
            h, m = divmod(m, 60)
            dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
            dur_sec = dur
        else:
            dur_str = dur
            dur_sec = time_to_seconds(dur)
            
        thumb = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL) if "thumbnails" in data else data.get("thumbnail")
        vidid = data.get("id", "")
        
        return title, dur_str, dur_sec, thumb, vidid

    # Wrappers
    async def title(self, link, videoid=None):
        t, _, _, _, _ = await self.details(link, videoid)
        return t

    async def duration(self, link, videoid=None):
        _, d, _, _, _ = await self.details(link, videoid)
        return d

    async def thumbnail(self, link, videoid=None):
        _, _, _, t, _ = await self.details(link, videoid)
        return t

    # ==========================
    # 📥 DOWNLOAD & STREAMING (The Fix)
    # ==========================
    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic,
        video: bool = False,
        videoid: Union[str, bool] = None
    ) -> Tuple[Optional[str], Optional[bool]]:
        
        await CookieManager.update_cookies()
        url = self._clean_url(link, videoid)
        cookie_file = CookieManager.get_cookie_file()

        # 1. LIVE STREAM CHECK (Fast CLI)
        if video:
            try:
                cmd = ["yt-dlp", "-g", url]
                if cookie_file: cmd.extend(["--cookies", cookie_file])
                out, _ = await run_async_cmd(cmd)
                if out and ".m3u8" in out.decode():
                    return out.decode().strip().split("\n")[0], None
            except: pass

        # 2. NATIVE PYTHON DOWNLOAD (Robust & Error Handling)
        def _native_download():
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
                'outtmpl': 'downloads/%(id)s.%(ext)s',
                'geo_bypass': True,
                'cookiefile': cookie_file,
                # Smart Format Selection: Prefer merged MP4, fallback to best available
                'format': 'bestvideo+bestaudio/best' if video else 'bestaudio/best',
                'writethumbnail': False,
                'noplaylist': True,
                'overwrites': True,
                'concurrent_fragment_downloads': 5,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=True)
                    if not info: return None
                    filename = ydl.prepare_filename(info)
                    
                    # Handle merged filenames (webm/mkv to mp4 logic usually handled by yt-dlp)
                    if os.path.exists(filename): return filename
                    
                    # Check common extensions if exact filename missing
                    base = filename.rsplit(".", 1)[0]
                    for ext in ["mp4", "mkv", "webm", "m4a", "mp3"]:
                        if os.path.exists(f"{base}.{ext}"):
                            return f"{base}.{ext}"
                    return None
                except Exception as e:
                    logger.error(f"Native DL Error: {e}")
                    return None

        # Execute Native Download in Thread
        filepath = await asyncio.to_thread(_native_download)
        
        if filepath and os.path.exists(filepath):
             return filepath, True
             
        # 3. CLI FALLBACK (Last Resort)
        # Sometimes CLI works when Library fails due to threading issues
        if not filepath:
             try:
                 fmt = "best" if video else "bestaudio"
                 cmd = ["yt-dlp", "-f", fmt, "-o", "downloads/%(id)s.%(ext)s", url]
                 if cookie_file: cmd.extend(["--cookies", cookie_file])
                 await run_async_cmd(cmd)
                 
                 # Check file again
                 vid_id = url.split("v=")[-1]
                 for ext in ["mp4", "mkv", "webm", "m4a", "mp3", "opus"]:
                     if os.path.exists(f"downloads/{vid_id}.{ext}"):
                         return f"downloads/{vid_id}.{ext}", True
             except: pass

        # 4. INTERNAL FALLBACK
        if await is_on_off(1):
             try:
                 title = await self.title(url)
                 p = await yt_dlp_download(url, type="video" if video else "audio", title=title)
                 if p: return p, True
             except: pass

        return None, None

    # ==========================
    # 📜 UTILITIES
    # ==========================
    @capture_internal_err
    async def playlist(self, link, limit, user_id, videoid=None):
        url = self._clean_url(link, videoid)
        if "playlist" not in url and videoid:
            url = f"https://youtube.com/playlist?list={videoid}"

        # Try python-lib
        try:
            pl = await Playlist.get(url)
            ids = [v['id'] for v in pl.get('videos', [])[:limit] if v.get('id')]
            if ids: return ids
        except: pass
        
        # CLI Fallback
        cookie = CookieManager.get_cookie_file()
        cmd = ["yt-dlp", "-i", "--flat-playlist", "--get-id", "--playlist-end", str(limit), url]
        if cookie: cmd.extend(["--cookies", cookie])
        
        out, _ = await run_async_cmd(cmd)
        return out.decode().strip().split("\n") if out else []

    @capture_internal_err
    async def track(self, link, videoid=None):
        try:
            d, _, _, t, vid = await self.details(link, videoid)
            return {
                "title": d,
                "link": f"{self.base}{vid}",
                "vidid": vid,
                "duration_min": "00:00",
                "thumb": t
            }, vid
        except:
            return {}, ""

    @capture_internal_err
    async def formats(self, link, videoid=None):
        url = self._clean_url(link, videoid)
        cookie = CookieManager.get_cookie_file()
        
        def _get_fmts():
            opts = {'quiet': True, 'cookiefile': cookie}
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        try:
            info = await asyncio.to_thread(_get_fmts)
            formats = []
            for f in info.get("formats", []):
                if "dash" in str(f.get("format")).lower(): continue
                formats.append({
                    "format": f.get("format_note", f.get("format_id")),
                    "filesize": f.get("filesize", 0),
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "yturl": url
                })
            return formats, url
        except: return [], url

    @capture_internal_err
    async def slider(self, link, query_type, videoid=None):
        url = self._clean_url(link, videoid)
        search = await VideosSearch(url, limit=15).next()
        results = search.get("result", [])
        if query_type >= len(results): return None, None, None, None
        item = results[query_type]
        return (
            item.get("title"),
            item.get("duration"),
            item.get("thumbnails", [{}])[0].get("url").split("?")[0],
            item.get("id")
        )

    @capture_internal_err
    async def video(self, link, videoid=None):
        url = self._clean_url(link, videoid)
        cookie = CookieManager.get_cookie_file()
        cmd = ["yt-dlp", "-g", "-f", "best[height<=720]", url]
        if cookie: cmd.extend(["--cookies", cookie])
        
        out, err = await run_async_cmd(cmd)
        if out: return 1, out.decode().split("\n")[0]
        return 0, str(err)

    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        if not message: return None
        msgs = [message]
        if message.reply_to_message: msgs.append(message.reply_to_message)
        for msg in msgs:
            text = msg.text or msg.caption or ""
            for ent in (msg.entities or msg.caption_entities or []):
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset:ent.offset+ent.length].split("&")[0]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url.split("&")[0]
        return None

    @capture_internal_err
    async def exists(self, link: str, videoid=None) -> bool:
        url = self._clean_url(link, videoid)
        return bool(re.search(self.regex, url))
