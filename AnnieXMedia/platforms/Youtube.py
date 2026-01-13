# Authored By Certified Coders © 2026
# 💎 THE DIAMOND EDITION: Full Features + Anti-Crash + Multi-Core 💎

import asyncio
import contextlib
import json
import os
import re
import time
import requests
from typing import Dict, List, Optional, Tuple, Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.aio import VideosSearch, Playlist

from AnnieXMedia.utils.cookie_handler import COOKIE_PATH
from AnnieXMedia.utils.database import is_on_off
from AnnieXMedia.utils.downloader import yt_dlp_download
from AnnieXMedia.utils.errors import capture_internal_err
from AnnieXMedia.utils.formatters import time_to_seconds
from AnnieXMedia.utils.tuning import YTDLP_TIMEOUT, YOUTUBE_META_MAX, YOUTUBE_META_TTL


# === Caches ===
_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()
_formats_cache: Dict[str, Tuple[float, List[Dict], str]] = {}
_formats_lock = asyncio.Lock()


# === Constants ===
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


# === 🍪 ULTIMATE COOKIE SYSTEM (ALEXA + BRANDRD LOGIC) ===
def _ensure_cookies() -> Optional[str]:
    """
    Scans for cookies in:
    1. ENV Variables (Upstream)
    2. Specific COOKIE_PATH
    3. 'cookies' directory (Auto-detect)
    """
    path = str(COOKIE_PATH)
    
    # 1. Check Env & Download if needed
    cookie_url = os.getenv("COOKIE_URL") or os.getenv("COOKIES_URL") or os.getenv("UPSTREAM_COOKIES")
    if cookie_url:
        try:
            if "batbin.me" in cookie_url and "/raw/" not in cookie_url:
                cookie_url = cookie_url.replace("batbin.me/", "batbin.me/raw/")
            elif "pastebin.com" in cookie_url and "/raw/" not in cookie_url:
                cookie_url = cookie_url.replace("pastebin.com/", "pastebin.com/raw/")
            
            response = requests.get(cookie_url, timeout=10)
            if response.status_code == 200:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(response.text)
                return path
        except:
            pass

    # 2. Check Specific Path
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path

    # 3. Scan Directory (The Alexa Way)
    try:
        cookie_dir = "cookies"
        if os.path.exists(cookie_dir):
            cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
            if cookies_files:
                return os.path.join(cookie_dir, cookies_files[0])
    except:
        pass
        
    return None


def _cookies_args() -> List[str]:
    path = _ensure_cookies()
    return ["--cookies", path] if path else []


# === ⚡ EXECUTOR ===
async def _exec_proc(*args: str) -> Tuple[bytes, bytes]:
    _ensure_cookies()
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        return await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        return b"", b"timeout"


@capture_internal_err
async def cached_youtube_search(query: str) -> List[Dict]:
    key = f"q:{query}"
    now = time.time()

    async with _cache_lock:
        if key in _cache:
            ts, val = _cache[key]
            if now - ts < YOUTUBE_META_TTL:
                return val
            _cache.pop(key, None)
        if len(_cache) > YOUTUBE_META_MAX:
            _cache.clear()

    try:
        data = await VideosSearch(query, limit=1).next()
        result = data.get("result", [])
    except Exception:
        result = []

    if result:
        async with _cache_lock:
            _cache[key] = (now, result)

    return result


# === Main Class ===
class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self._url_pattern = re.compile(r"(?:youtube\.com|youtu\.be)")
        
        # 🚀 GOD MODE FLAGS
        self.opts = [
            "--no-warnings", 
            "--ignore-errors", 
            "--geo-bypass", 
            "--nocheckcertificate",
            "--no-playlist",
            "--extractor-args", "youtube:player_client=android",
            "--concurrent-fragments", "4",
            "-o", "downloads/%(id)s.%(ext)s"
        ]

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            link = self.base_url + videoid.strip()

        link = link.strip()

        if "youtu.be" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]

        return link.split("&")[0]

    # === URL & Existence ===
    @capture_internal_err
    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        return bool(self._url_pattern.search(self._prepare_link(link, videoid)))

    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset: ent.offset + ent.length].split("&si")[0]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url.split("&si")[0]
        return None

    async def _ensure_watch_url(self, maybe_query_or_url: str) -> Optional[str]:
        prepared = self._prepare_link(maybe_query_or_url)
        if prepared.startswith("http"):
            return prepared
        data = await cached_youtube_search(prepared)
        if not data:
            return None
        vid = data[0].get("id")
        return self.base_url + vid if vid else None

    # === Metadata Fetching ===
    @capture_internal_err
    async def _fetch_video_info(self, query: str, *, use_cache: bool = True) -> Optional[Dict]:
        q = self._prepare_link(query)
        if use_cache and not q.startswith("http"):
            res = await cached_youtube_search(q)
            return res[0] if res else None
        data = await VideosSearch(q, limit=1).next()
        result = data.get("result", [])
        return result[0] if result else None

    @capture_internal_err
    async def is_live(self, link: str) -> bool:
        prepared = self._prepare_link(link)
        stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "--dump-json", prepared)
        if not stdout:
            return False
        try:
            info = json.loads(stdout.decode())
            return bool(info.get("is_live"))
        except json.JSONDecodeError:
            return False

    @capture_internal_err
    async def details(
        self, link: str, videoid: Union[str, bool, None] = None
    ) -> Tuple[str, Optional[str], int, str, str]:
        prepared_link = self._prepare_link(link, videoid)

        try:
            info = await self._fetch_video_info(prepared_link)
            if not info:
                raise ValueError("No results from youtubesearchpython (VideosSearch)")
        except Exception as search_err:
            raise ValueError("Video not found", {"cause": str(search_err)}) from search_err

        dt = info.get("duration")
        ds = int(time_to_seconds(dt)) if dt else 0
        thumb = (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[-1].get("url", "")
        ).split("?")[0]

        return info.get("title", ""), dt, ds, thumb, info.get("id", "")

    @capture_internal_err
    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("title", "") if info else ""

    @capture_internal_err
    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("duration") if info else None

    @capture_internal_err
    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[-1].get("url", "")
        ).split("?")[0] if info else ""

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        prepared_link = self._prepare_link(link, videoid)

        try:
            info = await self._fetch_video_info(prepared_link)
            if not info:
                raise ValueError("No results")
        except Exception as search_err:
            stdout, stderr = await _exec_proc(
                "yt-dlp", *(_cookies_args()), "--dump-json", "--no-warnings", prepared_link
            )

            if not stdout:
                raise ValueError(f"Both methods failed: {search_err}")

            try:
                info = json.loads(stdout.decode())
            except json.JSONDecodeError:
                raise ValueError("JSON Decode Error")

        thumb = (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[-1].get("url", "")
        ).split("?")[0]

        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", prepared_link),
            "vidid": info.get("id", ""),
            "duration_min": (
                info.get("duration")
                if isinstance(info.get("duration"), str)
                else None
            ),
            "thumb": thumb,
        }
        return details, info.get("id", "")

    # === Formats & Streams ===
    @capture_internal_err
    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        link = self._prepare_link(link, videoid)
        # Using a reliable format string for direct stream
        stdout, stderr = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "-g",
            "-f",
            "best[height<=?720]",
            link,
        )
        return (1, stdout.decode().split("\n")[0]) if stdout else (0, stderr.decode())

    @capture_internal_err
    async def playlist(
        self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None
    ) -> List[str]:
        if videoid:
            link = self.playlist_url + str(videoid)
        link = self._prepare_link(link).split("&")[0]

        try:
            plist = await Playlist.get(link)
            items = [video.get("id") for video in plist.get("videos", [])[:limit] if video.get("id")]
            if items:
                return items
        except Exception:
            pass

        stdout, _ = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "-i",
            "--get-id",
            "--flat-playlist",
            "--playlist-end",
            str(limit),
            "--skip-download",
            link,
        )
        items = stdout.decode().strip().split("\n") if stdout else []
        return [i for i in items if i]

    @capture_internal_err
    async def formats(
        self, link: str, videoid: Union[str, bool, None] = None
    ) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        key = f"f:{link}"
        now = time.time()

        async with _formats_lock:
            cached = _formats_cache.get(key)
            if cached and now - cached[0] < YOUTUBE_META_TTL:
                return cached[1], cached[2]

        cookies_file = _ensure_cookies()
        opts = {"quiet": True, "no_warnings": True, "ignoreerrors": True}
        if cookies_file:
            opts["cookiefile"] = cookies_file

        out: List[Dict] = []
        try:
            # Using ThreadPoolExecutor implicitly via to_thread logic if needed, 
            # but standard synchronous extract_info is safer here for raw metadata
            def _get_formats():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(link, download=False)
            
            info = await asyncio.to_thread(_get_formats)
            
            for fmt in info.get("formats", []):
                if "dash" in str(fmt.get("format", "")).lower():
                    continue
                # Relaxed checks to ensure we get *some* formats
                out.append(
                    {
                        "format": fmt.get("format"),
                        "filesize": fmt.get("filesize") or fmt.get("filesize_approx"),
                        "format_id": fmt.get("format_id"),
                        "ext": fmt.get("ext"),
                        "format_note": fmt.get("format_note"),
                        "yturl": link,
                    }
                )
        except Exception:
            pass

        async with _formats_lock:
            if len(_formats_cache) > YOUTUBE_META_MAX:
                _formats_cache.clear()
            _formats_cache[key] = (now, out, link)

        return out, link

    @capture_internal_err
    async def slider(
        self, link: str, query_type: int, videoid: Union[str, bool, None] = None
    ) -> Tuple[str, Optional[str], str, str]:
        data = await VideosSearch(self._prepare_link(link, videoid), limit=10).next()
        results = data.get("result", [])
        if not results or query_type >= len(results):
            raise IndexError(
                f"Query type index {query_type} out of range (found {len(results)} results)"
            )
        r = results[query_type]
        return (
            r.get("title", ""),
            r.get("duration"),
            r.get("thumbnails", [{}])[-1].get("url", "").split("?")[0],
            r.get("id", ""),
        )

    # === 🔥 THE CORE DOWNLOADER: FIXED & OPTIMIZED 🔥 ===
    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None]]:
        link = self._prepare_link(link, videoid)
        _ensure_cookies()
        cookies = _cookies_args()

        if video:
            if await self.is_live(link):
                status, stream_url = await self.video(link)
                if status == 1:
                    return stream_url, None
                return None, None

            # ☢️ ANTI-CRASH STRATEGY ☢️
            # 1. Best MP4 (No Merge) - 720p
            # 2. Best MP4 (No Merge) - 480p
            # 3. Best Anything (Last Resort)
            formats_to_try = [
                "best[height<=720][ext=mp4]", 
                "best[height<=480][ext=mp4]", 
                "best[ext=mp4]",
                "best"
            ]

            for fmt in formats_to_try:
                try:
                    cmd = [
                        "yt-dlp", *cookies, *self.opts,
                        "-f", fmt, link
                    ]
                    
                    proc = await asyncio.create_subprocess_exec(
                        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    await proc.communicate()

                    cmd_name = ["yt-dlp", "--get-filename", "-o", "downloads/%(id)s.%(ext)s", link]
                    name_proc = await asyncio.create_subprocess_exec(
                        *cmd_name, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    name_out, _ = await name_proc.communicate()
                    filename = name_out.decode().strip()

                    if os.path.exists(filename) and os.path.getsize(filename) > 0:
                        return filename, True
                except:
                    continue

            # Internal Fallback
            if await is_on_off(1):
                p = await yt_dlp_download(link, type="video", title=await self.title(link))
                return (p, True) if p else (None, None)

            return None, None

        # AUDIO MODE
        try:
            # Try M4A Direct (Fastest)
            cmd = ["yt-dlp", *cookies, *self.opts, "-f", "bestaudio[ext=m4a]/bestaudio/best", link]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            
            cmd_name = ["yt-dlp", "--get-filename", "-o", "downloads/%(id)s.%(ext)s", link]
            name_proc = await asyncio.create_subprocess_exec(
                *cmd_name, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            name_out, _ = await name_proc.communicate()
            filename = name_out.decode().strip()
            
            if os.path.exists(filename) and os.path.getsize(filename) > 0:
                return filename, True
        except:
            pass

        # Internal Fallback Audio
        p = await yt_dlp_download(link, type="audio", title=await self.title(link))
        return (p, True) if p else (None, None)
