# Authored By Certified Coders © 2025
"""
ذكي، سريع، وصارم: downloader مدعوم بـ yt-dlp + ffmpeg fallback.
تغييرات مهمة:
 - مجلدات منفصلة: downloads/audio/ و downloads/video/
 - أسماء كاش فريدة: <id>_<kind>_<safe-title-or-ts>.<ext>
 - TTL للكاش = 8 دقائق (from last access)
 - cleaner آمن لا يحذف الملفات المستخدمة
 - لا يستخدم aria2 على HLS/googlevideo manifests (لمنع 403)
 - لا يُرجع أبداً ملفات .m3u8 للمستهلك — يحوّلها إلى ملف نهائي
 - تسجيل (logging) منظم يميّز audio/video
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
import html
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

# ---------------- directories & naming ----------------
# base download dir (from core.dir)
AUDIO_DIR = os.path.join(DOWNLOAD_DIR, "audio")
VIDEO_DIR = os.path.join(DOWNLOAD_DIR, "video")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

# Cache TTL (8 minutes)
CACHE_TTL = 8 * 60  # seconds
_cache_registry: Dict[str, float] = {}
_cache_lock = asyncio.Lock()


# ---------------- Cache Manager ----------------
async def register_cache(path: str) -> None:
    """
    Register/extend cached file TTL (async).
    """
    if not path:
        return
    try:
        async with _cache_lock:
            _cache_registry[path] = time.time() + CACHE_TTL
            LOGGER.debug(f"register_cache: {os.path.basename(path)} expiry set to {int(_cache_registry[path])}")
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
    If anything unexpected occurs, assume file is in-use (fail-safe).
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
                            # renew short TTL if still in use
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
            LOGGER.debug("init_cache_cleaner: started")
        else:
            LOGGER.debug("init_cache_cleaner: event loop not running; cleaner not started")
    except Exception:
        LOGGER.exception("init_cache_cleaner failed")


# ---------------- helpers ----------------

def _safe_title_for_filename(title: str, fallback_ts: bool = True) -> str:
    """
    Produce a safe short token from title for filename.
    If title empty, use timestamp.
    """
    if not title:
        return str(int(time.time()))
    # unescape html entities, strip and keep alnum + dash + underscore
    s = html.unescape(title)
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", "_", s.strip())
    s = s[:40]
    return s or (str(int(time.time())) if fallback_ts else "")


def extract_video_id(link: str) -> str:
    """
    Try simple extraction of youtube id; otherwise empty.
    """
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


def find_cached_file(video_id: str, kind: Optional[str] = None) -> Optional[str]:
    """
    Search cache in kind-specific folder first, then fallback.
    """
    if not video_id:
        return None
    candidates = []
    if kind == "audio":
        search_dir = AUDIO_DIR
    elif kind == "video":
        search_dir = VIDEO_DIR
    else:
        # search both
        candidates.extend(glob.glob(os.path.join(AUDIO_DIR, f"{video_id}_*")))
        candidates.extend(glob.glob(os.path.join(VIDEO_DIR, f"{video_id}_*")))
        # also check legacy root filenames
        candidates.extend(glob.glob(os.path.join(DOWNLOAD_DIR, f"{video_id}.*")))

    if kind in ("audio", "video"):
        # prefer named files <id>_<kind>_<title>.<ext>
        for ext in ("mp3", "m4a", "mp4", "mkv", "webm", "opus"):
            p = os.path.join(search_dir, f"{video_id}_{kind}*.{ext}")
            matches = glob.glob(p)
            if matches:
                # newest first
                matches = sorted(matches, key=os.path.getmtime, reverse=True)
                _register_cache_from_thread(matches[0])
                return matches[0]
        # fallback to any file that starts with id in that dir
        matches_any = glob.glob(os.path.join(search_dir, f"{video_id}_*"))
        if matches_any:
            matches_any = sorted(matches_any, key=os.path.getmtime, reverse=True)
            _register_cache_from_thread(matches_any[0])
            return matches_any[0]

    # fallback: check both directories for any file with id prefix
    patterns = glob.glob(os.path.join(AUDIO_DIR, f"{video_id}_*")) + glob.glob(os.path.join(VIDEO_DIR, f"{video_id}_*"))
    if patterns:
        p = sorted(patterns, key=os.path.getmtime, reverse=True)[0]
        _register_cache_from_thread(p)
        return p

    # legacy fallback in root DOWNLOAD_DIR: id.ext
    for ext in ("mp4", "mkv", "webm", "m4a", "mp3", "opus"):
        p = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
        if os.path.exists(p):
            _register_cache_from_thread(p)
            return p

    return None


# ---------------- yt-dlp options & utils ----------------

def get_ytdlp_base_opts(verbose: bool = False, outtmpl: Optional[str] = None) -> Dict[str, object]:
    """
    Base options for yt-dlp; outtmpl if provided overrides default.
    Avoid enabling external_downloader for HLS/googlevideo links.
    """
    min_chunk = max(CHUNK_SIZE, 4 * 1024 * 1024)
    opts = {
        "outtmpl": outtmpl or os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
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

    # only add aria2 args by default; disabling later when necessary
    if ARIA2_PATH:
        opts["external_downloader"] = "aria2c"
        opts["external_downloader_args"] = ["-x", "4", "-k", "1M"]

    return opts


def _info_to_final_path(info: Dict, kind: str, out_dir: str) -> Optional[str]:
    """
    Find local final file path reported/created by yt-dlp inside out_dir.
    """
    if not isinstance(info, dict):
        return None
    vid = info.get("id")
    if not vid:
        return None
    ext = info.get("ext")
    if ext:
        p = os.path.join(out_dir, f"{vid}_{kind}.{ext}") if "_" not in vid else os.path.join(out_dir, f"{vid}.{ext}")
        # previous outputs may be saved as id.ext in out_dir
        # try common names
        # check id.ext first
        cand1 = os.path.join(out_dir, f"{vid}.{ext}")
        if os.path.exists(cand1):
            return cand1
        # try vid_kind.ext
        cand2 = os.path.join(out_dir, f"{vid}_{kind}.{ext}")
        if os.path.exists(cand2):
            return cand2
    # fallback: any file starting with id in out_dir
    matches = sorted(glob.glob(os.path.join(out_dir, f"{info.get('id','') }*")), key=os.path.getmtime, reverse=True)
    return matches[0] if matches else None


def _is_m3u8_url(url: str) -> bool:
    if not url:
        return False
    lower = url.lower()
    return lower.endswith(".m3u8") or ("manifest" in lower and "m3u8" in lower)


# ---------------- blocking helpers (run in executor) ----------------

def _ffmpeg_run_capture(cmd: str, timeout: int):
    """
    Run ffmpeg command and capture / log stderr head.
    """
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if proc.returncode == 0:
            LOGGER.debug(f"ffmpeg success cmd snippet: {cmd[:120]}...")
            return True
        stderr = (proc.stderr or "").strip().splitlines()
        head = "\n".join(stderr[:8])
        LOGGER.warning(f"ffmpeg failed (rc={proc.returncode}). stderr head:\n{head}")
        return False
    except subprocess.TimeoutExpired:
        LOGGER.warning("ffmpeg command timed out")
        return False
    except Exception as e:
        LOGGER.exception(f"ffmpeg execution error: {e}")
        return False


def _run_ffmpeg_convert(input_src: str, out_path: str) -> bool:
    """
    Convert an HLS manifest or remote URL to a local file.
    Try copy first (stream copy), then recode with veryfast preset.
    """
    try:
        # copy attempt (fast)
        cmd_copy = (
            f'ffmpeg -y -hide_banner -loglevel error '
            f'-fflags +nobuffer -flags low_delay -probesize 32 -analyzeduration 0 '
            f'-threads 0 -i {shlex.quote(input_src)} -c copy {shlex.quote(out_path)}'
        )
        ok = _ffmpeg_run_capture(cmd_copy, timeout=600)
        if ok and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            _register_cache_from_thread(out_path)
            return True

        # re-encode
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
            if ext == "opus":
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

        ok2 = _ffmpeg_run_capture(cmd_recode, timeout=900)
        if ok2 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            _register_cache_from_thread(out_path)
            return True
        LOGGER.debug(f"_run_ffmpeg_convert: conversion failed for {input_src}")
        return False
    except Exception as e:
        LOGGER.exception(f"ffmpeg conversion failed: {e}")
        return False


def _download_http_blocking(url: str, out_path: str, chunk_size: int = CHUNK_SIZE) -> bool:
    """
    Blocking HTTP download helper (used in executor) for direct URLs.
    """
    try:
        import requests
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
        LOGGER.debug(f"requests download failed: {e}")
        return False


# ---------------- naming finalization ----------------

def _ensure_named_final(candidate_path: str, desired_vid: str, kind: str, title_hint: str = "") -> Optional[str]:
    """
    Ensure final file name is <desired_vid>_<kind>_<safe-title>.<ext>.
    If candidate is a manifest (.m3u8), attempt convert -> final.
    """
    try:
        if not candidate_path:
            return None
        if not os.path.exists(candidate_path):
            return None

        safe = _safe_title_for_filename(title_hint)
        out_dir = AUDIO_DIR if kind == "audio" else VIDEO_DIR
        # choose extension
        _, ext = os.path.splitext(candidate_path)
        ext = ext.lstrip(".").lower() or ("mp4" if kind == "video" else "m4a")
        final_name = os.path.join(out_dir, f"{desired_vid}_{kind}_{safe}.{ext}")

        # If candidate is manifest -> convert into final_name
        if candidate_path.lower().endswith(".m3u8"):
            LOGGER.debug(f"_ensure_named_final: manifest -> converting {candidate_path} to {final_name}")
            ok = _run_ffmpeg_convert(candidate_path, final_name)
            if ok:
                try:
                    os.remove(candidate_path)
                except Exception:
                    pass
                _register_cache_from_thread(final_name)
                return final_name
            return None

        # candidate is file (move/copy if needed)
        if os.path.abspath(candidate_path) != os.path.abspath(final_name):
            try:
                shutil.move(candidate_path, final_name)
            except Exception:
                try:
                    shutil.copy(candidate_path, final_name)
                    os.remove(candidate_path)
                except Exception:
                    LOGGER.debug(f"_ensure_named_final: move/copy failed for {candidate_path} -> {final_name}")
                    return None
        _register_cache_from_thread(final_name)
        return final_name if os.path.exists(final_name) else None
    except Exception as e:
        LOGGER.debug(f"_ensure_named_final exception: {e}")
        return None


# ---------------- core sync ytdlp downloader (executor) ----------------

def download_with_ytdlp_sync(link: str, fmt: Optional[str] = None, verbose: bool = False, kind: str = "video", title_hint: str = "") -> Optional[str]:
    """
    Synchronous yt-dlp worker run in executor.
    Ensures final naming into audio/video dirs, and converts manifests. Disables aria2 for HLS/googlevideo links.
    """
    try:
        out_dir = AUDIO_DIR if kind == "audio" else VIDEO_DIR
        outtmpl = os.path.join(out_dir, "%(id)s.%(ext)s")
        base_opts = get_ytdlp_base_opts(verbose=verbose, outtmpl=outtmpl)

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
        desired_vid = extract_video_id(link) or _make_link_id(link)
        # check cache first
        existing = find_cached_file(desired_vid, kind=kind)
        if existing:
            LOGGER.debug(f"download_with_ytdlp_sync: served from cache {existing}")
            _register_cache_from_thread(existing)
            return existing

        for candidate in candidates:
            opts = dict(base_opts)
            opts["format"] = candidate

            # If original link looks like HLS/googlevideo manifest, disable external_downloader
            try:
                if ARIA2_PATH and (_is_m3u8_url(link) or "googlevideo.com" in link or "manifest.googlevideo" in link):
                    opts.pop("external_downloader", None)
                    opts.pop("external_downloader_args", None)
            except Exception:
                pass

            try:
                with YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(link, download=True)
                    # check yt-dlp produced file path(s)
                    reported = _info_to_final_path(info, kind=kind, out_dir=out_dir)
                    if reported and os.path.exists(reported):
                        final = _ensure_named_final(reported, desired_vid, kind, title_hint)
                        if final:
                            return final

                    # sometimes info contains url to manifest or direct url
                    url = None
                    if isinstance(info, dict):
                        url = info.get("url") or (info.get("requested_downloads") or [{}])[0].get("url")
                        if not url and info.get("entries"):
                            entry = info["entries"][0] if info["entries"] else {}
                            url = entry.get("url") if isinstance(entry, dict) else None

                    # if url is manifest -> convert via ffmpeg to final
                    if url and _is_m3u8_url(url):
                        target_ext = "mp4" if kind == "video" else "m4a"
                        out_path = os.path.join(out_dir, f"{desired_vid}_{kind}_{_safe_title_for_filename(title_hint)}.{target_ext}")
                        LOGGER.debug(f"download_with_ytdlp_sync: converting remote manifest URL -> {out_path}")
                        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                            _register_cache_from_thread(out_path)
                            return out_path
                        ok = _run_ffmpeg_convert(url, out_path)
                        if ok:
                            return out_path

                    # if url is direct http -> download with requests/aria2 allowed for non googlevideo
                    if url and url.startswith("http"):
                        ext_guess = url.split("?")[0].split(".")[-1][:8] or ("mp4" if kind == "video" else "m4a")
                        out_path = os.path.join(out_dir, f"{desired_vid}_{kind}_{_safe_title_for_filename(title_hint)}.{ext_guess}")
                        LOGGER.debug(f"download_with_ytdlp_sync: direct-url -> {out_path}")
                        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                            _register_cache_from_thread(out_path)
                            return out_path
                        # avoid aria2 for googlevideo/hls
                        if ARIA2_PATH and not (_is_m3u8_url(url) or "googlevideo.com" in url):
                            ok = _download_http_blocking(url, out_path)
                            if ok:
                                return out_path
                        ok = _download_http_blocking(url, out_path)
                        if ok:
                            return out_path

            except Exception as e:
                last_exc = e
                LOGGER.debug(f"yt-dlp attempt fmt={candidate} failed: {e}")
                continue

        LOGGER.error(f"All yt-dlp attempts failed for {link}. Last error: {last_exc}")
        return None
    except Exception as e:
        LOGGER.exception("download_with_ytdlp_sync fatal")
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

async def api_download_audio(link: str, title_hint: str = "") -> Optional[str]:
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
                    out = os.path.join(AUDIO_DIR, f"{vid}_audio_{_safe_title_for_filename(data.get('title', title_hint))}.{data.get('format','m4a')}")
                    res = await download_file(data.get("link"), out)
                    if res:
                        return res
                    return None
                if status == "error":
                    return None
                await asyncio.sleep(1)
    except Exception:
        return None


async def api_download_video(link: str, title_hint: str = "") -> Optional[str]:
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
                    out = os.path.join(VIDEO_DIR, f"{vid}_video_{_safe_title_for_filename(data.get('title',''))}.{data.get('format','mp4')}")
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
            LOGGER.debug(f"deduplicate_download: waiting on in-flight key {key}")
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


async def race_tasks(yt_task, api_task, title: str, kind: str):
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
                LOGGER.info(f"Track '{title or 'Unknown'}' ({kind}) - Downloaded by {src}")
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
                LOGGER.info(f"Track '{title or 'Unknown'}' ({kind}) - Downloaded by {src}")
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
    kind = "audio" if type == "audio" else "video"

    # compute a stable key id: prefer youtube id, else short hash of link
    vid = extract_video_id(link)
    if not vid:
        try:
            info = await loop.run_in_executor(None, lambda: YoutubeDL(get_ytdlp_base_opts()).extract_info(link, download=False))
            if isinstance(info, dict) and info.get("id"):
                vid = info.get("id")
        except Exception:
            vid = ""
    id_key = vid if vid else _make_link_id(link)

    # serve from cache if present (searches kind-specific directories)
    if vid and (cached := find_cached_file(vid, kind=kind)):
        if title:
            LOGGER.info(f"Track '{title}' ({kind}) - Served from cache -> {os.path.basename(cached)}")
        await register_cache(cached)
        return cached

    if type == "audio":
        key = f"audio:{id_key}"

        async def run():
            yt = asyncio.create_task(
                run_with_semaphore(
                    loop.run_in_executor(None, download_with_ytdlp_sync, link, "bestaudio[ext=m4a]/bestaudio/best", False, "audio", title)
                )
            )
            api = asyncio.create_task(api_download_audio(link, title)) if USE_AUDIO_API else None
            return await race_tasks(yt, api, title or "Unknown", "audio")

        result = await deduplicate_download(key, run)
        if result:
            await register_cache(result)
        return result

    if type == "video":
        key = f"video:{id_key}"

        async def run():
            fmt = "bestvideo[ext=mp4][vcodec!=?vp9][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            yt = asyncio.create_task(
                run_with_semaphore(
                    loop.run_in_executor(None, download_with_ytdlp_sync, link, fmt, False, "video", title)
                )
            )
            api = asyncio.create_task(api_download_video(link, title)) if USE_VIDEO_API else None
            return await race_tasks(yt, api, title or "Unknown", "video")

        result = await deduplicate_download(key, run)
        if result:
            await register_cache(result)
        return result

    return None
