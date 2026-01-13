# Authored By Certified Coders © 2025
"""
ذكي، سريع، وعملي: downloader مدعوم بـ yt-dlp + aiohttp + ffmpeg fallback.
تركيز هذا الإصدار: ضغط المعالجة، تجنب إعادة التكويد، تحويل HLS سريع (remux)، كاش 8 دقائق.
"""

import asyncio
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

# global queue DB to avoid deleting in-use files
from AnnieXMedia.misc import db as _GLOBAL_DB

LOGGER = LOGGER(__name__)

USE_AUDIO_API = bool(API_URL and API_KEY)
USE_VIDEO_API = bool(VIDEO_API_URL and API_KEY)

_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()

_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()

YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")

# ---------------- Cache Manager (8 minutes TTL) ----------------
CACHE_TTL = 8 * 60  # seconds
_cache_registry: Dict[str, float] = {}
_cache_lock = asyncio.Lock()


async def register_cache(path: str) -> None:
    if not path:
        return
    try:
        async with _cache_lock:
            _cache_registry[path] = time.time() + CACHE_TTL
    except Exception:
        _cache_registry[path] = time.time() + CACHE_TTL


def _register_cache_from_thread(path: str) -> None:
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
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_cache_cleaner_loop())
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
            _register_cache_from_thread(p)
            return p
    return None


# ---------------- yt-dlp options & utils ----------------

def get_ytdlp_base_opts(verbose: bool = False) -> Dict[str, object]:
    # pick a big chunk but not insane (depends on Fly.io memory)
    min_chunk = max(CHUNK_SIZE, 2 * 1024 * 1024)

    opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
        "quiet": not verbose,
        "no_warnings": not verbose,
        "noplaylist": True,
        "continuedl": True,
        "overwrites": False,
        "noprogress": True,
        "retries": 4,
        "fragment_retries": 4,
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

    # enable aria2c if available for throughput
    aria2_path = shutil.which("aria2c")
    if aria2_path:
        piece_len_k = max(512, min_chunk // 1024)
        opts["external_downloader"] = "aria2c"
        opts["external_downloader_args"] = [
            "-x", "16", "-s", "16", "-k", f"{piece_len_k}K",
            "--file-allocation=none", "--allow-overwrite=true",
            "--max-connection-per-server=16", "--min-split-size=1M"
        ]
        # if using aria2, lower concurrent_fragment_downloads to avoid double-splitting
        opts["concurrent_fragment_downloads"] = 8

    if cookie := get_cookie_file():
        opts["cookiefile"] = cookie

    return opts


def _info_to_final_path(info: Dict) -> Optional[str]:
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


# ---------------- ffmpeg remux helper (fast) ----------------

def force_remux_to_mp4(m3u8_url: str, video_id: str) -> Optional[str]:
    """
    Fast remux HLS -> mp4 using stream copy.
    Returns path or None.
    """
    out = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")
    # use protocol whitelist for safety; bsfa for aac ADTS -> MP4
    cmd = (
        f'ffmpeg -y -hide_banner -loglevel error '
        f'-protocol_whitelist file,http,https,tcp,tls '
        f'-i "{m3u8_url}" -c copy -bsf:a aac_adtstoasc "{out}"'
    )
    try:
        res = subprocess.run(cmd, shell=True, timeout=240)
        if res.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 0:
            _register_cache_from_thread(out)
            return out
    except Exception as e:
        LOGGER.debug(f"force_remux_to_mp4 failed: {e}")

    # fallback: try a low-cost transcode (use minimal CPU)
    try:
        out2 = os.path.join(DOWNLOAD_DIR, f"{video_id}_re.mp4")
        cmd2 = (
            f'ffmpeg -y -hide_banner -loglevel error '
            f'-protocol_whitelist file,http,https,tcp,tls '
            f'-i "{m3u8_url}" -c:v libx264 -preset superfast -crf 28 '
            f'-c:a aac -b:a 96k -ac 2 "{out2}"'
        )
        res2 = subprocess.run(cmd2, shell=True, timeout=300)
        if res2.returncode == 0 and os.path.exists(out2) and os.path.getsize(out2) > 0:
            _register_cache_from_thread(out2)
            return out2
    except Exception as e:
        LOGGER.debug(f"force_remux_to_mp4 fallback failed: {e}")

    return None


# ---------------- blocking helpers (run in executor) ----------------

def _download_http_blocking(url: str, out_path: str, chunk_size: int = CHUNK_SIZE) -> bool:
    import requests
    try:
        with requests.get(url, stream=True, timeout=(10, 200)) as r:
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


def _run_ffmpeg_convert(input_src: str, out_path: str) -> bool:
    """
    Try fast copy remux first, then minimal transcode.
    """
    # try copy (same as force_remux_to_mp4 but for local out_path)
    try:
        cmd_copy = (
            f'ffmpeg -y -hide_banner -loglevel error '
            f'-protocol_whitelist file,http,https,tcp,tls '
            f'-i {shlex.quote(input_src)} -c copy -bsf:a aac_adtstoasc {shlex.quote(out_path)}'
        )
        res = subprocess.run(cmd_copy, shell=True, timeout=300)
        if res.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            _register_cache_from_thread(out_path)
            return True
    except Exception as e:
        LOGGER.debug(f"ffmpeg copy failed: {e}")

    # fallback to a lightweight re-encode (low CPU quality)
    try:
        _, ext = os.path.splitext(out_path)
        ext = ext.lower().lstrip(".")
        if ext in ("mp4", "mkv", "webm"):
            cmd_recode = (
                f'ffmpeg -y -hide_banner -loglevel error -i {shlex.quote(input_src)} '
                f'-c:v libx264 -preset superfast -crf 28 -c:a aac -b:a 96k -ac 2 {shlex.quote(out_path)}'
            )
        else:
            cmd_recode = (
                f'ffmpeg -y -hide_banner -loglevel error -i {shlex.quote(input_src)} '
                f'-c:a aac -b:a 96k -ac 2 {shlex.quote(out_path)}'
            )
        res2 = subprocess.run(cmd_recode, shell=True, timeout=420)
        if res2.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            _register_cache_from_thread(out_path)
            return True
    except Exception as e:
        LOGGER.debug(f"ffmpeg recode failed: {e}")

    return False


# ---------------- core sync ytdlp downloader (used inside executor) ----------------

def download_with_ytdlp_sync(link: str, fmt: Optional[str] = None, verbose: bool = False) -> Optional[str]:
    """
    Runs in executor. Tries to return a local file (mp4/m4a/opus) not an m3u8.
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

                    # If yt-dlp returned an m3u8/manifest URL -> remux it to mp4
                    if url and _is_m3u8_url(url):
                        vid = info.get("id") or _safe_filename("video")
                        remuxed = force_remux_to_mp4(url, vid)
                        if remuxed:
                            return remuxed
                        # if remux failed, continue to next candidate (maybe direct file)
                        continue

                    # If yt-dlp returned a direct http URL (non-m3u8), try downloading it
                    if url and (url.startswith("http://") or url.startswith("https://")):
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
    loop = asyncio.get_running_loop()
    vid = extract_video_id(link)

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
