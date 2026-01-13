# Authored By Certified Coders © 2025
# ⚡ THE ULTIMATE EDITION: GOD SPEED + ZERO ERRORS + SMART FALLBACK ⚡
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


# === 🍪 ULTIMATE COOKIE SYSTEM ===
def _ensure_cookies() -> Optional[str]:
    """
    نظام ذكي جداً للكوكيز:
    1. يفحص المسار المباشر.
    2. يفحص متغيرات السيرفر (ENV) ويحملها لو مش موجودة.
    3. يفحص مجلد الكوكيز الاحتياطي.
    """
    path = str(COOKIE_PATH)
    
    # 1. Direct File Check
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path

    # 2. Env Variables (The Annie Way)
    cookie_url = os.getenv("COOKIE_URL") or os.getenv("COOKIES_URL") or os.getenv("UPSTREAM_COOKIES")
    if cookie_url:
        try:
            # Fix Raw Links
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

    # 3. Directory Scan (The Alexa Way)
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


# === ⚡ FAST PROCESS EXECUTOR ===
async def _exec_proc(*args: str) -> Tuple[bytes, bytes]:
    # تأكد من الكوكيز قبل أي عملية
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
        
        # 🚀 GOD MODE FLAGS: إعدادات السرعة القصوى
        self.turbo_flags = [
            "--concurrent-fragments", "5",       # تحميل 5 أجزاء في نفس الوقت
            "--resize-buffer",                   # تكبير الذاكرة المؤقتة
            "--http-chunk-size", "10M",          # تكبير حجم الحزمة
            "--retries", "10",                   # إعادة المحاولة 10 مرات لو النت فصل
            "--fragment-retries", "10",
            "--buffer-size", "1024",
            "--no-part",                         # عدم إنشاء ملفات .part (للسرعة)
            "--extractor-args", "youtube:player_client=android", # استخدام عميل أندرويد (أسرع وأخف)
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
            "best",
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
        # Optimization: Formats not needed for the download path, simplified.
        return [], link

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

    # === 🔥 THE MASTER DOWNLOADER 🔥 ===
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

        # إعدادات ثابتة للأمان والسرعة
        common_opts = [
            "--no-warnings", "--quiet",
            "--geo-bypass", "--nocheckcertificate",
            "--no-playlist",
            "-o", "downloads/%(id)s.%(ext)s"
        ]

        # 1. VIDEO DOWNLOAD LOGIC
        if video:
            if await self.is_live(link):
                status, stream_url = await self.video(link)
                if status == 1:
                    return stream_url, None
                return None, None

            # محاولات التحميل بالترتيب (من الأفضل للأضمن)
            # Try 1: 720p (Ideal)
            # Try 2: 480p (Fast)
            # Try 3: Best (Fail-safe)
            formats_to_try = [
                "bestvideo[height<=720]+bestaudio/best[height<=720]",
                "bestvideo[height<=480]+bestaudio/best[height<=480]",
                "best"
            ]

            cookies = _cookies_args()

            for fmt in formats_to_try:
                try:
                    cmd = [
                        "yt-dlp",
                        *cookies,
                        *self.turbo_flags,  # سرعة قصوى
                        *common_opts,
                        "-f", fmt,
                        link
                    ]
                    
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await proc.communicate()

                    # لو فشل بسبب الجودة، كمل للي بعده فوراً
                    if stderr and b"Requested format is not available" in stderr:
                        continue 
                    
                    # لو نجح، هات اسم الملف
                    cmd_name = ["yt-dlp", "--get-filename", "-o", "downloads/%(id)s.%(ext)s", link]
                    name_proc = await asyncio.create_subprocess_exec(
                        *cmd_name, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    name_out, _ = await name_proc.communicate()
                    filename = name_out.decode().strip()

                    if os.path.exists(filename) and os.path.getsize(filename) > 0:
                        return filename, True
                except:
                    continue # كمل للي بعده

            # Fallback (لو كل المحاولات فشلت - الطريقة القديمة)
            if await is_on_off(1):
                p = await yt_dlp_download(link, type="video", title=await self.title(link))
                return (p, True) if p else (None, None)
            
            return None, None

        # 2. AUDIO DOWNLOAD LOGIC
        try:
            cookies = _cookies_args()
            # الصوت: جودة M4A (عشان المكالمات) أو أي صوت، أو أي حاجة وخلاص
            fmt = "bestaudio[ext=m4a]/bestaudio/best"
            
            cmd = [
                "yt-dlp",
                *cookies,
                *self.turbo_flags,
                *common_opts,
                "-f", fmt,
                link
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
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

        # Fallback Audio
        p = await yt_dlp_download(link, type="audio", title=await self.title(link))
        return (p, True) if p else (None, None)
