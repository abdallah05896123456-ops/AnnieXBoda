# Authored By Certified Coders © 2025
"""
ذكي، سريع، وعملي: downloader مدعوم بـ yt-dlp + aiohttp + ffmpeg fallback.
معدل لإعطاء أعلى throughput عملي على Fly.io:
 - دعم aria2c كـ external_downloader إن وُجد
 - زيادة concurrent_fragment_downloads و http_chunk_size اعتمادًا على tuning.CHUNK_SIZE
 - إجبار اختيار صيغ MP4/H264 للسرعة والثبات (تجنب VP9 وm3u8 حينما يمكن)
 - تحويل m3u8 عبر ffmpeg مع -threads 0 و flags منخفضة الكمون
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

LOGGER = LOGGER(__name__)

USE_AUDIO_API = bool(API_URL and API_KEY)
USE_VIDEO_API = bool(VIDEO_API_URL and API_KEY)

_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()

_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()

YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


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
    if "v=" in s:
        return s.split("v=")[-1].split("&")[0]
    last = s.split("/")[-1].split("?")[0]
    return last if YOUTUBE_ID_RE.match(last) else ""


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
            return p
    return None


# ---------------- yt-dlp options & utils ----------------

def get_ytdlp_base_opts(verbose: bool = False) -> Dict[str, object]:
    """
    Aggressive-friendly base options.
    If aria2c is available as external_downloader, enable it with strong args.
    """
    # ensure a sensible minimum for chunk size
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
        # high but controlled concurrency for fragments
        "concurrent_fragment_downloads": 16,
        "http_chunk_size": min_chunk,
        "socket_timeout": 10,
        "cachedir": str(CACHE_DIR),
        "ignoreerrors": True,
        "merge_output_format": "mp4",
        # network helpers
        "nocheckcertificate": True,
        "geo_bypass": True,
        # prevent heavy postprocessing in yt-dlp
        "postprocessors": [],
        "recodevideo": None,
        "nopostoverwrites": True,
        # prefer ffmpeg for merges if needed
        "prefer_ffmpeg": True,
    }

    # enable aria2c if present (much faster for big files)
    aria2_path = shutil.which("aria2c")
    if aria2_path:
        # tune external_downloader args for throughput
        # piece length: try to give aria2 a chunk size in K/M (yt-dlp will pass this through)
        piece_len_k = max(1024, min_chunk // 1024)
        opts["external_downloader"] = "aria2c"
        opts["external_downloader_args"] = [
            "-x", "16",  # connections per server
            "-s", "16",  # split
            "-k", f"{piece_len_k}K",
            "--file-allocation=none",
            "--allow-overwrite=true",
            "--max-connection-per-server=16",
            "--min-split-size=1M",
        ]
        # reduce internal fragment concurrency when using aria2
        opts["concurrent_fragment_downloads"] = 8

    # add cookie file if exists
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
        # attempt a fast copy first
        cmd_copy = (
            f'ffmpeg -y -hide_banner -loglevel error '
            f'-fflags +nobuffer -flags low_delay -probesize 32 -analyzeduration 0 '
            f'-threads 0 -i {shlex.quote(input_src)} -c copy {shlex.quote(out_path)}'
        )
        res = subprocess.run(cmd_copy, shell=True, timeout=600)
        if res.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return True

        # fallback: re-encode quickly with sane stereo audio
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
        return res2.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0
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
        return os.path.exists(out_path)
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
    """
    try:
        base_opts = get_ytdlp_base_opts(verbose=verbose)

        # preferred format: try mp4/h264 + m4a audio first (fast to decode & stable)
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

            try:
                with YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(link, download=True)
                    final = _info_to_final_path(info)
                    if final and os.path.exists(final):
                        return final

                    # sometimes yt-dlp returns an URL (m3u8 or direct)
                    url = None
                    if isinstance(info, dict):
                        url = info.get("url") or (info.get("requested_downloads") or [{}])[0].get("url")
                        if not url and info.get("entries"):
                            entry = info["entries"][0] if info["entries"] else {}
                            url = entry.get("url") if isinstance(entry, dict) else None

                    # if url is an HLS manifest -> convert it locally (stable)
                    if url and _is_m3u8_url(url):
                        vid = info.get("id") or _safe_filename("video")
                        target_ext = "mp4" if not candidate.startswith("bestaudio") else "m4a"
                        out_path = os.path.join(DOWNLOAD_DIR, f"{vid}.{target_ext}")
                        ok = _run_ffmpeg_convert(url, out_path)
                        if ok:
                            return out_path

                    # if url is a direct HTTP media file -> download it (chunked)
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
        # connector limit=0 to allow many concurrent connections; Fly.io can handle multiple sockets
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
                    return await download_file(data.get("link"), out)
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
                    return await download_file(data.get("link"), out)
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
                # cancel pending
                for p in pending:
                    p.cancel()
                return result
        except Exception:
            pass
    # if none finished immediately, await remaining and return first valid
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
    vid = extract_video_id(link)

    # serve from cache if present
    if cached := find_cached_file(vid):
        if title:
            LOGGER.info(f"Track '{title}' - Served from cache")
        return cached

    if type == "audio":
        key = f"audio:{vid}"

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
        key = f"video:{vid}"

        async def run():
            # force mp4/h264 + m4a when possible; avoid handing m3u8 to player
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
