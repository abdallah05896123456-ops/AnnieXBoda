# Authored By Certified Coders © 2025
"""
ذكي، سريع، وعملي: downloader مدعوم بـ yt-dlp + aiohttp + ffmpeg fallback.
مميزات هذا الملف:
 - دعم aria2c كـ external_downloader إن كان متوفرًا (لكن **لا** يُستخدم على HLS/googlevideo manifests)
 - aggressive-friendly defaults (concurrent fragments, chunk size from tuning)
 - تحويل HLS (m3u8/manifest) إلى ملف محلي باستخدام ffmpeg عند الحاجة
 - نظام Cache مؤقت: يحفظ الملفات المحلية لمدة 8 دقائق منذ آخر استخدام، منظف خلفي يحذفها بأمان
 - تسجيل/تجديد TTL من كل نقاط الإرجاع
 - إصلاح dedupe key عند غياب video id (يستخدم هاش للرابط)
"""

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
from typing import Dict, Optional

import aiofiles
import aiohttp
from aiohttp import TCPConnector
from yt_dlp import YoutubeDL

from AnnieXMedia.core.dir import CACHE_DIR, DOWNLOAD_DIR
from AnnieXMedia.utils.cookie_handler import COOKIE_PATH as _COOKIES_FILE
from AnnieXMedia.utils.tuning import CHUNK_SIZE, SEM
from config import API_KEY, API_URL, VIDEO_API_URL
from AnnieXMedia.logging import LOGGER

# Access global db to avoid deleting files in-use
from AnnieXMedia.misc import db as _GLOBAL_DB

LOGGER = LOGGER(__name__)

USE_AUDIO_API = bool(API_URL and API_KEY)
USE_VIDEO_API = bool(VIDEO_API_URL and API_KEY)

_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()

_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()

YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")

# detect aria2 availability once
ARIA2_PATH = shutil.which("aria2c")


# ---------------- Cache Manager (8 minutes TTL) ----------------
CACHE_TTL = 8 * 60  # seconds
_cache_registry: Dict[str, float] = {}
_cache_lock = asyncio.Lock()


async def register_cache(path: str) -> None:
    """Register/extend cached file TTL (async)."""
    if not path:
        return
    try:
        async with _cache_lock:
            _cache_registry[path] = time.time() + CACHE_TTL
    except Exception:
        _cache_registry[path] = time.time() + CACHE_TTL


def _register_cache_from_thread(path: str) -> None:
    """
    Called from synchronous threads (like executor).
    Schedule the async register_cache safely if loop running, otherwise store directly.
    """
    if not path:
        return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(asyncio.create_task, register_cache(path))
        else:
            _cache_registry[path] = time.time() + CACHE_TTL
    except Exception:
        _cache_registry[path] = time.time() + CACHE_TTL


def _is_file_in_use(path: str) -> bool:
    """
    Return True if the file is referenced in the global db queue (playing/queued).
    Safe and forgiving: if structure unexpected we assume "in use".
    """
    try:
        for k, q in list(_GLOBAL_DB.items()):
            if not q:
                continue
            for item in q:
                if not isinstance(item, dict):
                    continue
                if item.get("file") == path or item.get("speed_path") == path:
                    return True
    except Exception:
        return True
    return False


async def _cache_cleaner_loop() -> None:
    """
    Background loop: remove expired cached files not currently in use.
    Runs until cancelled.
    """
    try:
        while True:
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
                    LOGGER.info(f"cache_cleaner: removed expired file {p}")
                except Exception as e:
                    LOGGER.debug(f"cache_cleaner: failed to remove {p}: {e}")
                async with _cache_lock:
                    _cache_registry.pop(p, None)
            await asyncio.sleep(30)
    except asyncio.CancelledError:
        return
    except Exception as e:
        LOGGER.exception(f"cache_cleaner fatal: {e}")


def init_cache_cleaner() -> None:
    """
    Start the background cleaner if event loop is running.
    Call this once during application startup (e.g. from core/call.py.start()).
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_cache_cleaner_loop())
        else:
            pass
    except Exception:
        LOGGER.exception("init_cache_cleaner failed")


# ---------------- helpers ----------------

def log_download_source(title: str, source: str) -> None:
    try:
        LOGGER.info(f"Track '{title}' - Downloaded by {source}")
    except Exception:
        print(f"[log] Track '{title}' - Downloaded by {source}")


def extract_video_id(link: str) -> str:
    if not link:
        return ""
    s = link.strip()
    if YOUTUBE_ID_RE.match(s):
        return s
    if "v=" in s and "youtube" in s:
        return s.split("v=")[-1].split("&")[0]
    last = s.split("/")[-1].split("?")[0]
    return last if YOUTUBE_ID_RE.match(last) else ""


def _make_link_id(link: str) -> str:
    """Return short deterministic id for arbitrary link (used when video id unavailable)."""
    if not link:
        return ""
    h = hashlib.sha256(link.encode()).hexdigest()
    return h[:16]


def get_cookie_file() -> Optional[str]:
    try:
        if _COOKIES_FILE and os.path.exists(_COOKIES_FILE) and os.path.getsize(_COOKIES_FILE) > 0:
            return _COOKIES_FILE
    except Exception:
        pass
    return None


def find_cached_file(video_id: str) -> Optional[str]:
    if not video_id:
        return None
    for ext in ("mp4", "mkv", "webm", "m4a", "mp3", "opus"):
        p = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
        if os.path.exists(p):
            _register_cache_from_thread(p)
            return p
    return None


# ---------------- yt-dlp options & utils ----------------

def get_ytdlp_base_opts(verbose: bool = False) -> Dict[str, object]:
    """
    Aggressive-friendly base options.
    external_downloader may be added later per-link (we avoid enabling it globally for HLS).
    """
    min_chunk = max(CHUNK_SIZE, 4 * 1024 * 1024)

    opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
        "quiet": not verbose,
        "no_warnings": not verbose,
        "noplaylist": True,
        "continuedl": True,
        "overwrites": False,
        "noprogress": True,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 16,
        "http_chunk_size": min_chunk,
        "socket_timeout": 10,
        "cachedir": str(CACHE_DIR),
        "ignoreerrors": True,
        "merge_output_format": "mp4",
        "nocheckcertificate": True,
        "geo_bypass": True,
        "postprocessors": [],
        "recodevideo": None,
        "nopostoverwrites": True,
        "prefer_ffmpeg": True,
    }

    if cookie := get_cookie_file():
        opts["cookiefile"] = cookie

    return opts


def _info_to_final_path(info: Dict) -> Optional[str]:
    """Find local final file path reported/created by yt-dlp"""
    if not isinstance(info, dict):
        return None
    vid = info.get("id")
    if not vid:
        return None
    ext = info.get("ext")
    if ext:
        p = os.path.join(DOWNLOAD_DIR, f"{vid}.{ext}")
        if os.path.exists(p):
            return p
    matches = sorted(
        glob.glob(os.path.join(DOWNLOAD_DIR, f"{vid}.*")),
        key=os.path.getmtime,
        reverse=True,
    )
    return matches[0] if matches else None


def _is_m3u8_url(url: str) -> bool:
    if not url:
        return False
    lower = url.lower()
    return lower.endswith(".m3u8") or ("manifest" in lower and "m3u8" in lower)


def _safe_filename(prefix: str = "tmp") -> str:
    ts = int(time.time() * 1000)
    return f"{prefix}_{ts}"


# ---------------- blocking helpers (run in executor) ----------------

def _run_ffmpeg_convert(input_src: str, out_path: str) -> bool:
    """
    Convert an HLS manifest or remote URL to a local file.
    Try copy first, then fast re-encode. Use -threads 0 to utilize CPUs.
    """
    try:
        cmd_copy = (
            f'ffmpeg -y -hide_banner -loglevel error '
            f'-fflags +nobuffer -flags low_delay -probesize 32 -analyzeduration 0 '
            f'-threads 0 -i {shlex.quote(input_src)} -c copy {shlex.quote(out_path)}'
        )
        res = subprocess.run(cmd_copy, shell=True, timeout=600)
        if res.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            _register_cache_from_thread(out_path)
            return True

        _, ext = os.path.splitext(out_path)
        ext = ext.lower().lstrip(".")
        if ext in ("mp4", "mkv", "webm"):
            cmd_recode = (
                f'ffmpeg -y -hide_banner -loglevel error '
                f'-fflags +nobuffer -flags low_delay -probesize 32 -analyzeduration 0 '
                f'-threads 0 -i {shlex.quote(input_src)} '
                f'-c:v libx264 -preset veryfast -crf 23 -c:a aac -b:a 160k -ac 2 -ar 48000 '
                f'{shlex.quote(out_path)}'
            )
        else:
            if ext in ("opus",):
                cmd_recode = (
                    f'ffmpeg -y -hide_banner -loglevel error '
                    f'-fflags +nobuffer -flags low_delay -probesize 32 -analyzeduration 0 '
                    f'-threads 0 -i {shlex.quote(input_src)} -c:a libopus -b:a 160k -ac 2 -ar 48000 {shlex.quote(out_path)}'
                )
            else:
                cmd_recode = (
                    f'ffmpeg -y -hide_banner -loglevel error '
                    f'-fflags +nobuffer -flags low_delay -probesize 32 -analyzeduration 0 '
                    f'-threads 0 -i {shlex.quote(input_src)} -c:a aac -b:a 160k -ac 2 -ar 48000 {shlex.quote(out_path)}'
                )

        res2 = subprocess.run(cmd_recode, shell=True, timeout=900)
        if res2.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            _register_cache_from_thread(out_path)
            return True
        return False
    except Exception as e:
        try:
            LOGGER.debug(f"ffmpeg conversion failed: {e}")
        except Exception:
            print("ffmpeg conversion failed:", e)
        return False


def _download_http_blocking(url: str, out_path: str, chunk_size: int = CHUNK_SIZE) -> bool:
    """
    Blocking HTTP download helper (used in executor) for direct URLs.
    """
    import requests
    try:
        with requests.get(url, stream=True, timeout=(10, 180)) as r:
            r.raise_for_status()
            with open(out_path, "wb") as fh:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        fh.write(chunk)
        if os.path.exists(out_path):
            _register_cache_from_thread(out_path)
            return True
        return False
    except Exception as e:
        try:
            LOGGER.debug(f"requests download failed: {e}")
        except Exception:
            print("requests download failed:", e)
        return False


# ---------------- core sync ytdlp downloader (used inside executor) ----------------

def download_with_ytdlp_sync(link: str, fmt: Optional[str] = None, verbose: bool = False) -> Optional[str]:
    """
    Synchronous worker for yt-dlp (runs in executor).
    Prioritizes MP4/H264 outputs and avoids returning HLS manifests when possible.
    Also disables aria2 external_downloader when link is HLS/googlevideo to avoid 403 on shards.
    """
    try:
        base_opts = get_ytdlp_base_opts(verbose=verbose)

        preferred = "bestvideo[ext=mp4][vcodec!=?vp9][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best"

        candidates = []
        if fmt:
            candidates.append(fmt)
        candidates.extend([
            preferred,
            "bestaudio[ext=m4a]/bestaudio/best",
            "bestaudio/best",
            "bestvideo[height<=1080]+bestaudio/best",
            "best"
        ])

        last_exc = None
        for candidate in candidates:
            opts = dict(base_opts)
            opts["format"] = candidate

            # If the original link looks like HLS/googlevideo manifest, disable external_downloader
            try:
                if ARIA2_PATH and ( _is_m3u8_url(link) or "googlevideo.com" in link or "manifest.googlevideo" in link ):
                    opts.pop("external_downloader", None)
                    opts.pop("external_downloader_args", None)
            except Exception:
                pass

            try:
                with YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(link, download=True)
                    final = _info_to_final_path(info)
                    if final and os.path.exists(final):
                        _register_cache_from_thread(final)
                        return final

                    url = None
                    if isinstance(info, dict):
                        url = info.get("url") or (info.get("requested_downloads") or [{}])[0].get("url")
                        if not url and info.get("entries"):
                            entry = info["entries"][0] if info["entries"] else {}
                            url = entry.get("url") if isinstance(entry, dict) else None

                    if url and _is_m3u8_url(url):
                        vid = info.get("id") or _safe_filename("video")
                        target_ext = "mp4" if not candidate.startswith("bestaudio") else "m4a"
                        out_path = os.path.join(DOWNLOAD_DIR, f"{vid}.{target_ext}")
                        ok = _run_ffmpeg_convert(url, out_path)
                        if ok:
                            return out_path

                    if url and url.startswith("http"):
                        vid = info.get("id") or _safe_filename("direct")
                        ext = url.split("?")[0].split(".")[-1][:8] or "dat"
                        out_path = os.path.join(DOWNLOAD_DIR, f"{vid}.{ext}")
                        ok = _download_http_blocking(url, out_path)
                        if ok:
                            return out_path

            except Exception as e:
                last_exc = e
                try:
                    LOGGER.debug(f"yt-dlp attempt fmt={candidate} failed: {e}")
                except Exception:
                    print(f"[yt-dlp-debug] fmt={candidate} -> {e}")
                continue

        try:
            LOGGER.error(f"All yt-dlp attempts failed for {link}. Last error: {last_exc}")
        except Exception:
            print("All yt-dlp attempts failed:", last_exc)
        return None
    except Exception as e:
        try:
            LOGGER.exception("download_with_ytdlp_sync fatal")
        except Exception:
            print("download_with_ytdlp_sync fatal:", e)
        return None


# ---------------- async helpers ----------------

async def get_http_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    async with _session_lock:
        if _session and not _session.closed:
            return _session
        timeout = aiohttp.ClientTimeout(total=600, sock_connect=20, sock_read=60)
        connector = TCPConnector(limit=0, ttl_dns_cache=300, enable_cleanup_closed=True)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _session


async def close_http_session() -> None:
    global _session
    async with _session_lock:
        if _session and not _session.closed:
            await _session.close()
        _session = None


async def download_file(url: str, out_path: str) -> Optional[str]:
    """
    Async download using aiohttp (used by API wrappers).
    """
    if not url:
        return None
    try:
        session = await get_http_session()
        async with session.get(url) as resp:
            if resp.status != 200:
                LOGGER.debug(f"download_file http status {resp.status} for {url}")
                return None
            async with aiofiles.open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    if not chunk:
                        break
                    await f.write(chunk)
        if os.path.exists(out_path):
            await register_cache(out_path)
        return out_path if os.path.exists(out_path) else None
    except Exception as e:
        LOGGER.debug(f"download_file exception: {e}")
        return None


# ---------------- api download wrappers ----------------

async def api_download_audio(link: str) -> Optional[str]:
    if not USE_AUDIO_API:
        return None
    vid = extract_video_id(link)
    if not vid:
        return None
    url = f"{API_URL}/song/{vid}?api={API_KEY}"
    try:
        session = await get_http_session()
        while True:
            async with session.get(url) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                status = str(data.get("status", "")).lower()
                if status == "done":
                    out = os.path.join(DOWNLOAD_DIR, f"{vid}.{data.get('format','webm')}")
                    res = await download_file(data.get("link"), out)
                    if res:
                        return res
                    return None
                if status == "error":
                    return None
                await asyncio.sleep(1)
    except Exception:
        return None


async def api_download_video(link: str) -> Optional[str]:
    if not USE_VIDEO_API:
        return None
    vid = extract_video_id(link)
    if not vid:
        return None
    url = f"{VIDEO_API_URL}/video/{vid}?api={API_KEY}"
    try:
        session = await get_http_session()
        while True:
            async with session.get(url) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                status = str(data.get("status", "")).lower()
                if status == "done":
                    out = os.path.join(DOWNLOAD_DIR, f"{vid}.{data.get('format','mp4')}")
                    res = await download_file(data.get("link"), out)
                    if res:
                        return res
                    return None
                if status == "error":
                    return None
                await asyncio.sleep(1)
    except Exception:
        return None


# ---------------- orchestration ----------------

async def run_with_semaphore(coro):
    async with SEM:
        return await coro


async def deduplicate_download(key: str, runner):
    async with _inflight_lock:
        if fut := _inflight.get(key):
            return await fut
        fut = asyncio.get_running_loop().create_future()
        _inflight[key] = fut
    try:
        res = await runner()
        fut.set_result(res)
        return res
    except Exception as e:
        try:
            fut.set_exception(e)
        except Exception:
            pass
        return None
    finally:
        async with _inflight_lock:
            _inflight.pop(key, None)


async def race_tasks(yt_task, api_task, title: str):
    # race between yt-dlp and optional API; return the first successful file path
    tasks = {t for t in (yt_task, api_task) if t}
    if not tasks:
        return None
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in done:
        try:
            result = t.result()
            if result and os.path.exists(result):
                src = "yt-dlp" if t is yt_task else "API"
                log_download_source(title or "Unknown", src)
                for p in pending:
                    p.cancel()
                return result
        except Exception:
            pass
    for p in pending:
        try:
            res = await p
            if res and os.path.exists(res):
                src = "yt-dlp" if p is yt_task else "API"
                log_download_source(title or "Unknown", src)
                return res
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    return None


# ---------------- public API ----------------

async def yt_dlp_download(link: str, type: str, title: str = "") -> Optional[str]:
    """
    Public async wrapper:
      link: URL or video id
      type: "audio" or "video"
    Returns local file path or None.
    """
    loop = asyncio.get_running_loop()

    # compute a stable key id: prefer youtube id, else short hash of link
    vid = extract_video_id(link)
    id_key = vid if vid else _make_link_id(link)

    # serve from cache if present (only works for real video id files named by id)
    if vid and (cached := find_cached_file(vid)):
        if title:
            LOGGER.info(f"Track '{title}' - Served from cache")
        return cached

    if type == "audio":
        key = f"audio:{id_key}"

        async def run():
            yt = asyncio.create_task(
                run_with_semaphore(
                    loop.run_in_executor(None, download_with_ytdlp_sync, link, "bestaudio[ext=m4a]/bestaudio/best", False)
                )
            )
            api = asyncio.create_task(api_download_audio(link)) if USE_AUDIO_API else None
            return await race_tasks(yt, api, title or "Unknown")

        return await deduplicate_download(key, run)

    if type == "video":
        key = f"video:{id_key}"

        async def run():
            fmt = "bestvideo[ext=mp4][vcodec!=?vp9][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            yt = asyncio.create_task(
                run_with_semaphore(
                    loop.run_in_executor(None, download_with_ytdlp_sync, link, fmt, False)
                )
            )
            api = asyncio.create_task(api_download_video(link)) if USE_VIDEO_API else None
            return await race_tasks(yt, api, title or "Unknown")

        return await deduplicate_download(key, run)

    return None
