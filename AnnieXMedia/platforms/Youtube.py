# file: AnnieXMedia/platforms/Youtube.py
# YouTube helper: metadata, url extraction, direct links, is_live
import asyncio
import contextlib
import json
import os
import re
import time
import logging
from typing import Dict, List, Optional, Tuple, Union
from concurrent.futures import ThreadPoolExecutor

import yt_dlp
from youtubesearchpython.aio import VideosSearch

# Pyrogram types for url extraction
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

logger = logging.getLogger("AnnieXMedia.YouTube")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# CONFIG
YTDLP_TIMEOUT = 30
YOUTUBE_META_TTL = 3600
YOUTUBE_META_MAX = 400
MAX_WORKERS = 12

# USE RAM if possible
if os.path.exists("/dev/shm"):
    DOWNLOAD_PATH = "/dev/shm/AnnieDownloads"
else:
    DOWNLOAD_PATH = os.path.abspath("downloads")
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

POSSIBLE_COOKIE_PATHS = [
    "AnnieXMedia/assets/cookies.txt",
    "cookies.txt",
    "AnnieXMedia/cookies.txt",
    "assets/cookies.txt",
    "platforms/cookies.txt",
    "/app/cookies.txt",
]

ARIA2_ARGS = ["-x", "16", "-s", "16", "-j", "16", "-k", "1M", "--file-allocation=none", "--disable-ipv6=true"]

_cache: Dict[str, Tuple[float, Tuple[Dict, str]]] = {}
_cache_lock = asyncio.Lock()
_formats_cache: Dict[str, Tuple[float, List[Dict], str]] = {}
_formats_lock = asyncio.Lock()


def get_cookie_file() -> Optional[str]:
    for p in POSSIBLE_COOKIE_PATHS:
        try:
            if os.path.exists(p) and os.path.getsize(p) > 0:
                return p
        except Exception:
            continue
    return None


async def _exec_proc(*args: str, timeout: int = YTDLP_TIMEOUT) -> Tuple[bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        return await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        return b"", b"timeout"


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.listbase = "https://youtube.com/playlist?list="
        self._url_pattern = re.compile(r"(?:youtube\.com|youtu\.be)")
        self.pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            link = self.base + videoid.strip()
        link = (link or "").strip()
        if "youtu.be" in link:
            link = self.base + link.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            link = self.base + link.split("/")[-1].split("?")[0]
        return link.split("&")[0]

    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        return bool(self._url_pattern.search(self._prepare_link(link, videoid)))

    # extract url from Message (works for reply and entities)
    async def url(self, message: Message) -> Optional[str]:
        if not message:
            return None
        msgs = [message]
        if getattr(message, "reply_to_message", None):
            msgs.append(message.reply_to_message)
        for msg in msgs:
            text = getattr(msg, "text", None) or getattr(msg, "caption", None) or ""
            entities = (getattr(msg, "entities", None) or []) + (getattr(msg, "caption_entities", None) or [])
            for ent in entities:
                try:
                    if ent.type == MessageEntityType.URL:
                        return text[ent.offset: ent.offset + ent.length].split("&si")[0]
                    if ent.type == MessageEntityType.TEXT_LINK:
                        return ent.url.split("&si")[0]
                except Exception:
                    continue
        return None

    # use youtubesearchpython cache-first, fallback to yt-dlp
    async def _fetch_video_info(self, query: str, *, use_cache: bool = True) -> Optional[Dict]:
        q = self._prepare_link(query)
        if use_cache and q and not q.startswith("http"):
            key = f"q:{q}"
            now = time.time()
            async with _cache_lock:
                if key in _cache:
                    ts, (val, vid) = _cache[key]
                    if now - ts < YOUTUBE_META_TTL:
                        return val
                    _cache.pop(key, None)
        try:
            res = await VideosSearch(q or query, limit=1).next()
            result = res.get("result", [])
        except Exception:
            result = []
        if result:
            async with _cache_lock:
                _cache[f"q:{q}"] = (time.time(), (result[0], result[0].get("id", "")))
            return result[0]

        # fallback: yt-dlp dump-json
        cookie = get_cookie_file()
        cmd = ["yt-dlp"]
        if cookie:
            cmd += ["--cookies", cookie]
        cmd += ["--dump-json", q or query]
        stdout, stderr = await _exec_proc(*cmd, timeout=20)
        if stdout:
            try:
                info = json.loads(stdout.decode(errors="ignore"))
                return info
            except Exception:
                return None
        return None

    async def is_live(self, link: str) -> bool:
        prepared = self._prepare_link(link)
        cookie = get_cookie_file()
        cmd = ["yt-dlp"]
        if cookie:
            cmd += ["--cookies", cookie]
        cmd += ["--dump-json", prepared]
        stdout, stderr = await _exec_proc(*cmd, timeout=20)
        if not stdout:
            return False
        try:
            info = json.loads(stdout.decode(errors="ignore"))
            return bool(info.get("is_live"))
        except Exception:
            return False

    async def details(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], int, str, str]:
        prepared = self._prepare_link(link, videoid)
        info = await self._fetch_video_info(prepared)
        if not info:
            raise ValueError("Video not found")
        dt = info.get("duration")
        ds = int(self._to_seconds(dt)) if dt else 0
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[-1].get("url", "")).split("?")[0]
        return info.get("title", ""), dt, ds, thumb, info.get("id", "")

    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("title", "") if info else ""

    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("duration") if info else None

    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return (info.get("thumbnail") or info.get("thumbnails", [{}])[-1].get("url", "")).split("?")[0] if info else ""

    # try direct link via yt-dlp -g (fast)
    async def direct_link(self, link: str, videoid: Union[str, bool, None] = None, *, prefer_audio=False) -> Optional[str]:
        link = self._prepare_link(link, videoid)
        cookie = get_cookie_file()
        cmd = ["yt-dlp"]
        if cookie:
            cmd += ["--cookies", cookie]
        cmd += ["--compat-options", "no-youtube-unavailable-videos"]
        if prefer_audio:
            cmd += ["-g", "-f", "bestaudio[ext=m4a]/bestaudio"]
        else:
            cmd += ["-g", "-f", "best[height<=720]"]
        cmd.append(link)
        stdout, stderr = await _exec_proc(*cmd, timeout=15)
        if stdout:
            return stdout.decode().splitlines()[0].strip()
        return None

    async def formats(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        key = f"f:{link}"
        now = time.time()
        async with _formats_lock:
            cached = _formats_cache.get(key)
            if cached and now - cached[0] < YOUTUBE_META_TTL:
                return cached[1], cached[2]
        ytdl_opts = {"quiet": True}
        if cf := get_cookie_file():
            ytdl_opts["cookiefile"] = cf
        out: List[Dict] = []
        try:
            with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                for fmt in info.get("formats", []):
                    fs = fmt.get("filesize") or fmt.get("filesize_approx")
                    if not fs:
                        continue
                    out.append({
                        "format": fmt.get("format"),
                        "filesize": fs,
                        "format_id": fmt.get("format_id"),
                        "ext": fmt.get("ext"),
                        "format_note": fmt.get("format_note"),
                    })
        except Exception as e:
            logger.debug("formats extract failed: %s", e)
        async with _formats_lock:
            if len(_formats_cache) > YOUTUBE_META_MAX:
                _formats_cache.clear()
            _formats_cache[key] = (now, out, link)
        return out, link

    def _to_seconds(self, t: Optional[str]) -> int:
        if not t:
            return 0
        try:
            parts = [int(p) for p in str(t).split(":")]
            s = 0
            for p in parts:
                s = s * 60 + p
            return s
        except Exception:
            return 0


# exported instance
YouTube = YouTubeAPI()
