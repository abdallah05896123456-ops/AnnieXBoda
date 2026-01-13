# Authored By Certified Coders © 2025
import asyncio
import contextlib
import glob
import os
import re
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


# -------------------- helpers --------------------

def log_download_source(title: str, source: str) -> None:
    LOGGER.info(f"Track '{title}' - Downloaded by {source}")


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
    for ext in ("webm", "m4a", "mp3", "mp4", "mkv"):
        p = f"{DOWNLOAD_DIR}/{video_id}.{ext}"
        if os.path.exists(p):
            return p
    return None


# -------------------- yt-dlp --------------------

def get_ytdlp_base_opts() -> Dict[str, object]:
    opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "continuedl": True,
        "overwrites": False,
        "noprogress": True,
        "retries": 2,
        "fragment_retries": 2,
        "concurrent_fragment_downloads": 8,
        "http_chunk_size": 1 << 20,
        "socket_timeout": 20,
        "cachedir": str(CACHE_DIR),
        "ignoreerrors": True,
        "merge_output_format": "mp4",
    }
    if cookie := get_cookie_file():
        opts["cookiefile"] = cookie
    return opts


def get_final_path_from_info(info: Dict) -> Optional[str]:
    vid = info.get("id")
    if not vid:
        return None
    matches = sorted(
        glob.glob(f"{DOWNLOAD_DIR}/{vid}.*"),
        key=os.path.getmtime,
        reverse=True,
    )
    return matches[0] if matches else None


def download_with_ytdlp_sync(link: str, fmt: str) -> Optional[str]:
    try:
        opts = get_ytdlp_base_opts()
        opts["format"] = fmt
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=False)
            if cached := get_final_path_from_info(info):
                return cached
            ydl.download([link])
            return get_final_path_from_info(info)
    except Exception as e:
        LOGGER.error(f"yt-dlp error: {e}")
        return None


# -------------------- http api --------------------

async def get_http_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    async with _session_lock:
        if _session and not _session.closed:
            return _session
        timeout = aiohttp.ClientTimeout(total=600)
        connector = TCPConnector(limit=0, ttl_dns_cache=300)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _session


async def download_file(url: str, out_path: str) -> Optional[str]:
    try:
        session = await get_http_session()
        async with session.get(url) as r:
            if r.status != 200:
                return None
            async with aiofiles.open(out_path, "wb") as f:
                async for chunk in r.content.iter_chunked(CHUNK_SIZE):
                    await f.write(chunk)
        return out_path
    except Exception:
        return None


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
                data = await r.json()
                if data.get("status") == "done":
                    out = f"{DOWNLOAD_DIR}/{vid}.{data.get('format','webm')}"
                    return await download_file(data["link"], out)
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
                data = await r.json()
                if data.get("status") == "done":
                    out = f"{DOWNLOAD_DIR}/{vid}.{data.get('format','mp4')}"
                    return await download_file(data["link"], out)
                await asyncio.sleep(1)
    except Exception:
        return None


# -------------------- orchestration --------------------

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
    finally:
        async with _inflight_lock:
            _inflight.pop(key, None)


async def race(yt_task, api_task, title):
    done, pending = await asyncio.wait(
        {t for t in (yt_task, api_task) if t},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for t in done:
        if t.result():
            log_download_source(title, "yt-dlp" if t is yt_task else "API")
            for p in pending:
                p.cancel()
            return t.result()
    return None


# -------------------- public api --------------------

async def yt_dlp_download(link: str, type: str, title: str = "") -> Optional[str]:
    loop = asyncio.get_running_loop()
    vid = extract_video_id(link)

    if cached := find_cached_file(vid):
        return cached

    if type == "audio":
        key = f"audio:{vid}"

        async def run():
            yt = asyncio.create_task(
                run_with_semaphore(
                    loop.run_in_executor(
                        None,
                        download_with_ytdlp_sync,
                        link,
                        "bestaudio/best",
                    )
                )
            )
            api = asyncio.create_task(api_download_audio(link)) if USE_AUDIO_API else None
            return await race(yt, api, title)

        return await deduplicate_download(key, run)

    if type == "video":
        key = f"video:{vid}"

        async def run():
            yt = asyncio.create_task(
                run_with_semaphore(
                    loop.run_in_executor(
                        None,
                        download_with_ytdlp_sync,
                        link,
                        "bestvideo[height<=720]+bestaudio/best",
                    )
                )
            )
            api = asyncio.create_task(api_download_video(link)) if USE_VIDEO_API else None
            return await race(yt, api, title)

        return await deduplicate_download(key, run)

    return None
