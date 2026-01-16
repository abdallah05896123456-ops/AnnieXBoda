# Authored By Certified Coders © 2025
# Hyperion Engine Integrated + Failover System
# Modified: integrated robust Hyperion API usage + improved failover and error handling

import asyncio
import contextlib
import json
import os
import re
import time
import pathlib
from typing import Dict, List, Optional, Tuple, Union

import aiohttp
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.aio import VideosSearch, Playlist

from AnnieXMedia.utils.cookie_handler import COOKIE_PATH
from AnnieXMedia.utils.database import is_on_off
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
# ⚡ رابط السيرفر الخاص بك (الأولوية الأولى)
HYPERION_API_URL = "https://hyperionengine.fly.dev".rstrip("/")

# Helper paths
DOWNLOADS_DIR = pathlib.Path("downloads")
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

# === Helpers ===
def _cookiefile_path() -> Optional[str]:
    path = str(COOKIE_PATH)
    try:
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    except Exception:
        pass
    return None


def _cookies_args() -> List[str]:
    path = _cookiefile_path()
    return ["--cookies", path] if path else []


async def _exec_proc(*args: str) -> Tuple[bytes, bytes]:
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

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            link = self.base_url + videoid.strip()

        link = link.strip()

        if "youtu.be" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]

        return link.split("&")[0]

    # === URL Handling ===
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
                raise ValueError(
                    f"No results from youtubesearchpython (VideosSearch) "
                    f"for query/URL: '{prepared_link}'"
                )
        except Exception as search_err:
            stdout, stderr = await _exec_proc(
                "yt-dlp", *(_cookies_args()), "--dump-json", "--no-warnings", prepared_link
            )

            def _both_failed(details: str) -> ValueError:
                return ValueError(
                    f"Both methods failed for '{prepared_link}':\n"
                    f"  1. youtubesearchpython error: {search_err}\n"
                    f"{details}"
                )

            if not stdout:
                stderr_msg = stderr.decode().strip() if stderr else "Empty response"
                raise _both_failed(f"  2. yt-dlp error: {stderr_msg}")

            try:
                info = json.loads(stdout.decode())
            except json.JSONDecodeError as json_err:
                raw = stdout.decode()[:400]
                raise _both_failed(
                    f"  2. yt-dlp JSON error: {json_err}\n"
                    f"     Raw: {raw}..."
                ) from json_err

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

    # === Media & Formats ===
    @capture_internal_err
    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        link = self._prepare_link(link, videoid)
        stdout, stderr = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
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

        opts = {"quiet": True}
        if cf := _cookiefile_path():
            opts["cookiefile"] = cf

        out: List[Dict] = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                for fmt in info.get("formats", []):
                    if "dash" in str(fmt.get("format", "")).lower():
                        continue
                    if not any(k in fmt for k in ("filesize", "filesize_approx")):
                        continue
                    if not all(k in fmt for k in ("format", "format_id", "ext", "format_note")):
                        continue
                    size = fmt.get("filesize") or fmt.get("filesize_approx")
                    if not size:
                        continue
                    out.append(
                        {
                            "format": fmt["format"],
                            "filesize": size,
                            "format_id": fmt["format_id"],
                            "ext": fmt["ext"],
                            "format_note": fmt["format_note"],
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

    # 🔥🔥🔥 الدالة الذكية (Hybrid Download) 🔥🔥🔥
    # 1. Hyperion API (Priority)
    # 2. Local Failover (Backup)
    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None]]:
        """
        Returns:
            (stream_url, False) => stream_url is an HTTP(S) URL that the bot can stream directly
            (local_path, True)  => local file path (absolute) that the bot can use as fallback
            (None, None)        => failed
        """
        link = self._prepare_link(link, videoid)
        loop = asyncio.get_running_loop()

        # ==========================
        # 🚀 المرحلة 1: محاولة الـ API (Hyperion)
        # ==========================
        try:
            print(f"⚡ [Hyperion] Trying Cloud Engine for: {link}")
            payload = {
                "url": link,
                "type": "video" if video else "audio",
                "requester": "AnnieX_Bot",
            }

            # Use aiohttp for non-blocking HTTP
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.post(f"{HYPERION_API_URL}/api/v1/download", data=payload) as resp:
                        status_code = resp.status
                        # Accept 200 or 202 (queued)
                        if status_code not in (200, 201, 202):
                            text = await resp.text()
                            print(f"⚠️ [Hyperion] Server responded with status {status_code}: {text[:200]}")
                        else:
                            data = await resp.json(content_type=None)
                            job_id = data.get("job_id")
                            if job_id:
                                print(f"⏳ [Hyperion] Job Started: {job_id}")
                                # Polling loop up to ~45 seconds (30 * 1.5s)
                                poll_attempts = 30
                                for _ in range(poll_attempts):
                                    try:
                                        async with session.get(f"{HYPERION_API_URL}/api/v1/status/{job_id}", timeout=5) as sres:
                                            if sres.status == 200:
                                                status_data = await sres.json(content_type=None)
                                                state = status_data.get("status")
                                                if state == "completed":
                                                    # Prefer download_url if provided
                                                    final_url = status_data.get("download_url") or status_data.get("file_path")
                                                    if final_url:
                                                        # If file_path returned (just filename), build full URL
                                                        if final_url.startswith("/"):
                                                            stream_url = HYPERION_API_URL + final_url
                                                        elif final_url.startswith("http://") or final_url.startswith("https://"):
                                                            stream_url = final_url
                                                        else:
                                                            # try /downloads/<filename> first (static), then /api/v1/file/
                                                            fname = final_url
                                                            # if it's a path like downloads/xxx.mp3, extract filename
                                                            if "/" in fname:
                                                                fname = fname.split("/")[-1]
                                                            stream_url = f"{HYPERION_API_URL}/downloads/{fname}"
                                                        print(f"🚀 [Hyperion] Success! Stream URL: {stream_url}")
                                                        return stream_url, False
                                                    else:
                                                        print("⚠️ [Hyperion] Completed but no download_url/file_path returned.")
                                                        break
                                                elif state == "failed":
                                                    print("❌ [Hyperion] Job Failed. Switching to Local...")
                                                    break
                                            else:
                                                # non-200 from status endpoint: continue
                                                pass
                                    except Exception as e:
                                        # transient error, continue polling
                                        # print minimal for debug
                                        # print(f"⚠️ [Hyperion] Poll error: {e}")
                                        pass
                                    await asyncio.sleep(1.5)
                            else:
                                print("❌ [Hyperion] No Job ID in response.")
                except asyncio.TimeoutError:
                    print("⚠️ [Hyperion] Request timed out (initial post).")
                except Exception as e:
                    print(f"⚠️ [Hyperion] Connection error: {e}")

        except Exception as e:
            print(f"⚠️ [Hyperion] Connection Skipped: {e}")

        # ==========================
        # 🛡️ المرحلة 2: التحميل المحلي (Failover)
        # ==========================
        print("🔄 [System] Switching to Local Download (Failover Mode)...")

        def audio_dl():
            opts = {
                # إعدادات معدلة لتجنب خطأ Empty File
                "format": "bestaudio[ext=m4a]/bestaudio/best",
                "outtmpl": str(DOWNLOADS_DIR / "%(id)s.%(ext)s"),
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "ignoreerrors": True,  # تجاهل الأخطاء الطفيفة
                "prefer_ffmpeg": True,
            }
            if cf := _cookiefile_path():
                opts["cookiefile"] = cf

            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(link, download=False)
                    ext = info.get("ext") or "m4a"
                    fid = info.get("id") or ""
                    xyz = str(DOWNLOADS_DIR / f"{fid}.{ext}")
                    if os.path.exists(xyz) and os.path.getsize(xyz) > 0:
                        return os.path.abspath(xyz)
                    ydl.download([link])
                    if os.path.exists(xyz) and os.path.getsize(xyz) > 0:
                        return os.path.abspath(xyz)
                    # attempt to find any file starting with id
                    for f in DOWNLOADS_DIR.iterdir():
                        if f.name.startswith(fid):
                            return str(f.resolve())
                    return None
            except Exception as e:
                print(f"❌ [Local] Audio DL Error: {e}")
                return None

        def video_dl():
            opts = {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "outtmpl": str(DOWNLOADS_DIR / "%(id)s.%(ext)s"),
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "ignoreerrors": True,
            }
            if cf := _cookiefile_path():
                opts["cookiefile"] = cf

            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(link, download=False)
                    ext = info.get("ext") or "mp4"
                    fid = info.get("id") or ""
                    xyz = str(DOWNLOADS_DIR / f"{fid}.{ext}")
                    if os.path.exists(xyz) and os.path.getsize(xyz) > 0:
                        return os.path.abspath(xyz)
                    ydl.download([link])
                    if os.path.exists(xyz) and os.path.getsize(xyz) > 0:
                        return os.path.abspath(xyz)
                    for f in DOWNLOADS_DIR.iterdir():
                        if f.name.startswith(fid):
                            return str(f.resolve())
                    return None
            except Exception as e:
                print(f"❌ [Local] Video DL Error: {e}")
                return None

        # تنفيذ التحميل المحلي
        if video:
            if await self.is_live(link):
                status, stream_url = await self.video(link)
                if status == 1:
                    return stream_url, None
                return None, None

            downloaded_file = await loop.run_in_executor(None, video_dl)
            return (downloaded_file, True) if downloaded_file else (None, None)

        downloaded_file = await loop.run_in_executor(None, audio_dl)
        return (downloaded_file, True) if downloaded_file else (None, None)
