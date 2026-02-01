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
from typing import Dict, List, Tuple, Optional, Union
from concurrent.futures import ThreadPoolExecutor

import yt_dlp
from youtubesearchpython.aio import VideosSearch

logger = logging.getLogger("AnnieXMedia.YouTube")
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
        link = link.strip()
        if "youtu.be" in link:
            link = self.base + link.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            link = self.base + link.split("/")[-1].split("?")[0]
        return link.split("&")[0]

    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        return bool(self._url_pattern.search(self._prepare_link(link, videoid)))

    # ----- metadata fetch with cache -----
    async def _fetch_video_info_vsp(self, query: str, *, use_cache: bool = True) -> Optional[Dict]:
        q = self._prepare_link(query)
        if use_cache and not q.startswith("http"):
            key = f"q:{q}"
            now = time.time()
            async with _cache_lock:
                if key in _cache:
                    ts, (val, vid) = _cache[key]
                    if now - ts < YOUTUBE_META_TTL:
                        return val
                    _cache.pop(key, None)
        try:
            res = await VideosSearch(q, limit=1).next()
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
                "postprocessors": [
                    # keep minimal: user code can run ffmpeg embed if needed
                ],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])

            # Attempt to find thumbnail & embed if possible
            try:
                # find downloaded file (by id)
                # yt-dlp's prepare_filename could be complex; fallback: find newest file in DOWNLOAD_PATH
                files = sorted(
                    (os.path.join(DOWNLOAD_PATH, p) for p in os.listdir(DOWNLOAD_PATH)),
                    key=lambda p: os.path.getmtime(p),
                    reverse=True
                )
                if files:
                    download_file = files[0]
                    # try to get thumbnail separately
                    thumb_dest = os.path.join(DOWNLOAD_PATH, f"thumb_{int(time.time())}.jpg")
                    # use yt-dlp to write thumbnail
                    tf_opts = {"skip_download": True, "writethumbnail": True, "outtmpl": thumb_dest}
                    try:
                        with yt_dlp.YoutubeDL({"quiet": True, "cookiefile": get_cookie_file(), "writethumbnail": True, "skip_download": True}) as ydl2:
                            ydl2.download([link])
                        # find thumb in DOWNLOAD_PATH
                        thumbs = [os.path.join(DOWNLOAD_PATH, f) for f in os.listdir(DOWNLOAD_PATH) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
                        if thumbs:
                            thumb_file = thumbs[0]
                            # embed thumbnail using ffmpeg (if file is mp4/m4a)
                            out_file = download_file + ".thumbed"
                            cmd = [
                                "ffmpeg", "-y", "-i", download_file, "-i", thumb_file,
                                "-map", "0", "-map", "1", "-c", "copy",
                                "-disposition:v:0", "attached_pic", out_file
                            ]
                            with contextlib.suppress(Exception):
                                subprocess_proc = shutil.which("ffmpeg")
                                if subprocess_proc:
                                    import subprocess
                                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                                    # replace file if succeeded
                                    if os.path.exists(out_file):
                                        os.replace(out_file, download_file)
            except Exception:
                logger.debug("postprocessing (thumb embed) failed", exc_info=True)

        except Exception as e:
            logger.debug("background download failed: %s", e, exc_info=True)

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
            except Exception as e:
                logger.exception("sync download failed: %s", e)
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
        cmd = ["yt-dlp", "-i", "--compat-options", "no-youtube-unavailable-videos", "--get-id", "--flat-playlist", "--playlist-end", str(limit), "--skip-download", link]
        stdout, stderr = await _exec_proc_with_timeout(*cmd, timeout=60)
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
