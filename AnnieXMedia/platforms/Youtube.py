# file: AnnieXMedia/platforms/Youtube.py
# Unified YouTube helper: direct-links, background cache (aria2c), piping-friendly
# Requires: yt-dlp, youtubesearchpython, ffmpeg, aria2c (recommended)

import asyncio
import contextlib
import json
import os
import re
import time
import logging
import shutil
import subprocess
from typing import Dict, List, Tuple, Optional, Union
from concurrent.futures import ThreadPoolExecutor

import yt_dlp
from youtubesearchpython.aio import VideosSearch

# Pyrogram types for url extraction
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

logger = logging.getLogger("AnnieXMedia.YouTube")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# ---- config ----
YTDLP_TIMEOUT = 30
YOUTUBE_META_TTL = 3600
YOUTUBE_META_MAX = 300
MAX_WORKERS = 16

# download/cache path (use RAM if available)
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
    "cookies/cookies.txt",
]

# aria2c args (tweak if needed)
ARIA2_ARGS = ["-x", "16", "-s", "16", "-j", "16", "-k", "1M", "--file-allocation=none", "--disable-ipv6=true"]

# caches
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


async def _exec_proc_with_timeout(*args: str, timeout: int = YTDLP_TIMEOUT) -> Tuple[bytes, bytes]:
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

    # ---------------------------
    # New: extract url from Message (compatible with old interface)
    # ---------------------------
    async def url(self, message: Message) -> Optional[str]:
        """
        Extract URL from a pyrogram Message or its reply (entities/text_link).
        Returns the first found URL (str) or None.
        """
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
                        # entity offset/length safe slicing
                        return text[ent.offset: ent.offset + ent.length].split("&si")[0]
                    if ent.type == MessageEntityType.TEXT_LINK:
                        return ent.url.split("&si")[0]
                except Exception:
                    # skip malformed entities
                    continue
        return None

    # ----- metadata fetch with cache -----
    async def _fetch_video_info_vsp(self, query: str, *, use_cache: bool = True) -> Optional[Dict]:
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
        return None

    async def is_live(self, link: str) -> bool:
        prepared = self._prepare_link(link)
        cookie = get_cookie_file()
        cmd = ["yt-dlp"]
        if cookie:
            cmd += ["--cookies", cookie]
        cmd += ["--dump-json", prepared]
        stdout, stderr = await _exec_proc_with_timeout(*cmd)
        if not stdout:
            return False
        try:
            info = json.loads(stdout.decode(errors="ignore"))
            return bool(info.get("is_live"))
        except Exception:
            return False

    # ---- details/title/duration/thumbnail/track ----
    async def details(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], int, str, str]:
        prepared = self._prepare_link(link, videoid)
        info = await self._fetch_video_info_vsp(prepared)
        if not info:
            raise ValueError("Video not found")
        dt = info.get("duration")
        ds = int(self._to_seconds(dt)) if dt else 0
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[-1].get("url", "")).split("?")[0]
        return info.get("title", ""), dt, ds, thumb, info.get("id", "")

    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info_vsp(self._prepare_link(link, videoid))
        return info.get("title", "") if info else ""

    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        info = await self._fetch_video_info_vsp(self._prepare_link(link, videoid))
        return info.get("duration") if info else None

    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info_vsp(self._prepare_link(link, videoid))
        return (info.get("thumbnail") or info.get("thumbnails", [{}])[-1].get("url", "")).split("?")[0] if info else ""

    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        prepared = self._prepare_link(link, videoid)
        info = await self._fetch_video_info_vsp(prepared)
        if not info:
            # fallback to yt-dlp dump-json
            cookie = get_cookie_file()
            cmd = ["yt-dlp"]
            if cookie:
                cmd += ["--cookies", cookie]
            cmd += ["--dump-json", prepared]
            stdout, stderr = await _exec_proc_with_timeout(*cmd)
            if not stdout:
                return {"title": "Unknown", "link": prepared, "vidid": "", "duration_min": None, "thumb": ""}, ""
            try:
                info = json.loads(stdout.decode(errors="ignore"))
            except Exception:
                return {"title": "Unknown", "link": prepared, "vidid": "", "duration_min": None, "thumb": ""}, ""
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[-1].get("url", "")).split("?")[0]
        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", prepared),
            "vidid": info.get("id", ""),
            "duration_min": info.get("duration") if isinstance(info.get("duration"), str) else None,
            "thumb": thumb,
        }
        return details, info.get("id", "")

    # ---- formats with cache ----
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
                    fdict = {
                        "format": fmt.get("format"),
                        "filesize": fs,
                        "format_id": fmt.get("format_id"),
                        "ext": fmt.get("ext"),
                        "format_note": fmt.get("format_note"),
                        "yturl": link,
                    }
                    out.append(fdict)
        except Exception as e:
            logger.debug("formats extract failed: %s", e)
        async with _formats_lock:
            if len(_formats_cache) > YOUTUBE_META_MAX:
                _formats_cache.clear()
            _formats_cache[key] = (now, out, link)
        return out, link

    # ---- video direct link (fast-path) ----
    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        link = self._prepare_link(link, videoid)
        cookie = get_cookie_file()
        cmd = ["yt-dlp"]
        if cookie:
            cmd += ["--cookies", cookie]
        cmd += ["--compat-options", "no-youtube-unavailable-videos"]
        cmd += ["-g", "-f", "best[height<=?720][width<=?1280]", link]
        stdout, stderr = await _exec_proc_with_timeout(*cmd)
        if stdout:
            return 1, stdout.decode().splitlines()[0].strip()
        return 0, (stderr or b"").decode(errors="ignore")

    # ---- background downloader (sync; runs in threadpool) ----
    def _background_download(self, link: str, final_path: str, is_video: bool):
        try:
            fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]" if is_video else "bestaudio[ext=m4a]/bestaudio/best"
            ydl_opts = {
                "format": fmt,
                "outtmpl": final_path,
                "cookiefile": get_cookie_file(),
                "quiet": True,
                "no_warnings": True,
                "external_downloader": "aria2c",
                "external_downloader_args": ARIA2_ARGS,
                "prefer_ffmpeg": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
        except Exception:
            logger.debug("background download failed", exc_info=True)

        # try postprocessing (thumbnail embedding) in its own safe block
        try:
            # search for the most-recent file in DOWNLOAD_PATH (best-effort)
            files = sorted(
                (os.path.join(DOWNLOAD_PATH, p) for p in os.listdir(DOWNLOAD_PATH) if os.path.isfile(os.path.join(DOWNLOAD_PATH, p))),
                key=lambda p: os.path.getmtime(p),
                reverse=True
            )
            if not files:
                return
            download_file = files[0]
            # attempt to download thumbnail via yt-dlp writethumbnail (best-effort)
            try:
                with yt_dlp.YoutubeDL({"quiet": True, "cookiefile": get_cookie_file(), "skip_download": True, "writethumbnail": True, "outtmpl": os.path.join(DOWNLOAD_PATH, "thumb.%(ext)s")}) as ydl2:
                    ydl2.download([link])
                thumbs = [os.path.join(DOWNLOAD_PATH, f) for f in os.listdir(DOWNLOAD_PATH) if f.lower().startswith("thumb.") and f.lower().endswith((".jpg", ".jpeg", ".png"))]
                if thumbs:
                    thumb_file = thumbs[0]
                    out_file = download_file + ".thumbed"
                    ffmpeg_bin = shutil.which("ffmpeg")
                    if ffmpeg_bin:
                        cmd = [
                            ffmpeg_bin, "-y", "-i", download_file, "-i", thumb_file,
                            "-map", "0", "-map", "1", "-c", "copy",
                            "-disposition:v:0", "attached_pic", out_file
                        ]
                        try:
                            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                            if os.path.exists(out_file):
                                os.replace(out_file, download_file)
                        except Exception:
                            logger.debug("ffmpeg embed failed", exc_info=True)
            except Exception:
                logger.debug("thumbnail write attempt failed", exc_info=True)
        except Exception:
            logger.debug("postprocessing final block failed", exc_info=True)

    # ---- download unified ----
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        songaudio: Union[bool, str, None] = None,
        songvideo: Union[bool, str, None] = None,
        format_id: Union[str, bool, None] = None,
        title: Union[str, bool, None] = None,
    ) -> Tuple[Optional[str], bool]:
        link = self._prepare_link(link, videoid)

        # check live first
        try:
            if await self.is_live(link):
                status, stream = await self.video(link)
                if status == 1 and stream:
                    # spawn background cache and return direct stream
                    loop = asyncio.get_running_loop()
                    final_path = os.path.join(DOWNLOAD_PATH, f"{int(time.time())}.mp4" if video else f"{int(time.time())}.m4a")
                    loop.run_in_executor(self.pool, self._background_download, link, final_path, bool(video))
                    return stream, True
        except Exception:
            logger.debug("is_live check failed", exc_info=True)

        # attempt fast-path direct link
        cookie = get_cookie_file()
        cmd = ["yt-dlp"]
        if cookie:
            cmd += ["--cookies", cookie]
        cmd += ["--compat-options", "no-youtube-unavailable-videos"]
        if video:
            cmd += ["-g", "-f", "best[height<=720]"]
        else:
            cmd += ["-g", "-f", "bestaudio[ext=m4a]/bestaudio"]
        cmd.append(link)

        stdout, stderr = await _exec_proc_with_timeout(*cmd)
        if stdout:
            direct = stdout.decode().splitlines()[0].strip()
            # start background cache
            loop = asyncio.get_running_loop()
            final_path = os.path.join(DOWNLOAD_PATH, f"{int(time.time())}.{ 'mp4' if video else 'm4a'}")
            loop.run_in_executor(self.pool, self._background_download, link, final_path, bool(video))
            return direct, True

        # fallback: synchronous download in threadpool (blocking)
        loop = asyncio.get_running_loop()

        def _sync_dl():
            try:
                fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]" if video else "bestaudio[ext=m4a]/bestaudio/best"
                ydl_opts = {
                    "format": fmt,
                    "outtmpl": os.path.join(DOWNLOAD_PATH, "%(id)s.%(ext)s"),
                    "cookiefile": get_cookie_file(),
                    "quiet": True,
                    "no_warnings": True,
                    "external_downloader": "aria2c",
                    "external_downloader_args": ARIA2_ARGS,
                    "prefer_ffmpeg": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=True)
                    filename = ydl.prepare_filename(info)
                    return filename
            except Exception:
                logger.exception("sync download failed", exc_info=True)
                return None

        downloaded = await loop.run_in_executor(self.pool, _sync_dl)
        if downloaded:
            return downloaded, False
        return None, False

    # ---- playlist fast ----
    async def playlist(self, link: str, limit: int, user_id=None, videoid: Union[str, bool, None] = None) -> List[str]:
        if videoid:
            link = self.listbase + str(link)
        link = self._prepare_link(link)
        stdout, stderr = await _exec_proc_with_timeout("yt-dlp", "-i", "--compat-options", "no-youtube-unavailable-videos", "--get-id", "--flat-playlist", "--playlist-end", str(limit), "--skip-download", link, timeout=60)
        if stdout:
            return [s for s in stdout.decode().splitlines() if s]
        return []

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
