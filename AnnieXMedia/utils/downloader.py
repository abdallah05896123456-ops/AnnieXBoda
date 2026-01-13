# Authored By Certified Coders © 2025
"""
ذكي، سريع، وعملي: downloader مدعوم بـ yt-dlp + aiohttp + ffmpeg fallback.
صُمّم ليعمل داخل مشروع AnnieXMedia مع نفس المتغيرات (DOWNLOAD_DIR, CACHE_DIR, SEM, CHUNK_SIZE).
"""

import asyncio
import contextlib
import glob
import os
import re
import shlex
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
    for ext in ("mp4", "mkv", "webm", "m4a", "mp3"):
        p = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
        if os.path.exists(p):
            return p
    return None


# ---------------- yt-dlp options & utils ----------------

def get_ytdlp_base_opts(verbose: bool = False) -> Dict[str, object]:
    # خيارات أساسية جيدة للسرعة والاستقرار
    opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
        "quiet": not verbose,
        "no_warnings": not verbose,
        "noplaylist": True,
        "continuedl": True,
        "overwrites": False,
        "noprogress": True,
        "retries": 2,
        "fragment_retries": 2,
        "concurrent_fragment_downloads": 8,
        "http_chunk_size": 1 << 20,  # 1 MiB chunk
        "socket_timeout": 30,
        "cachedir": str(CACHE_DIR),
        "ignoreerrors": True,
        # حاول تسهيل الدمج لو احتجنا:
        "merge_output_format": "mp4",
    }
    if cookie := get_cookie_file():
        opts["cookiefile"] = cookie
    return opts


def _info_to_final_path(info: Dict) -> Optional[str]:
    """ابحث عن ملف محلي مطابق للمعلومة info التي أعادها yt-dlp"""
    if not isinstance(info, dict):
        return None
    vid = info.get("id")
    if not vid:
        return None
    # أفضل محاولة: امتداد مذكور داخل info
    ext = info.get("ext")
    if ext:
        p = os.path.join(DOWNLOAD_DIR, f"{vid}.{ext}")
        if os.path.exists(p):
            return p
    # ابحث بأي امتداد متاح
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
    return lower.endswith(".m3u8") or "manifest" in lower and "m3u8" in lower


def _safe_filename(prefix: str = "tmp") -> str:
    ts = int(time.time() * 1000)
    return f"{prefix}_{ts}"


# ---------------- blocking helpers (run in executor) ----------------

def _run_ffmpeg_convert(input_src: str, out_path: str) -> bool:
    """
    استدعي ffmpeg لتحويل مقطع (مثلاً m3u8 أو URL) إلى ملف MP4 محلي.
    نجرب copy codecs إن أمكن ثم fallback لإعادة التكويد.
    """
    try:
        # أولًا حاول نسخة مباشرة (ممكن تفشل إن كانت الدفق يحتاج إعادة تغليف)
        cmd_copy = f'ffmpeg -y -hide_banner -loglevel error -i {shlex.quote(input_src)} -c copy {shlex.quote(out_path)}'
        res = subprocess.run(cmd_copy, shell=True)
        if res.returncode == 0 and os.path.exists(out_path):
            return True
        # لو فشل، جرب ترميز بسيط
        cmd_recode = f'ffmpeg -y -hide_banner -loglevel error -i {shlex.quote(input_src)} -c:v libx264 -preset veryfast -c:a aac -b:a 128k {shlex.quote(out_path)}'
        res2 = subprocess.run(cmd_recode, shell=True)
        return res2.returncode == 0 and os.path.exists(out_path)
    except Exception as e:
        try:
            LOGGER.debug(f"ffmpeg conversion failed: {e}")
        except Exception:
            print("ffmpeg conversion failed:", e)
        return False


def _download_http_blocking(url: str, out_path: str, chunk_size: int = 1 << 20) -> bool:
    """
    تحميل بسيط متزامن (يُشغل في executor) للمساعدة مع روابط مباشرة.
    """
    import requests
    try:
        with requests.get(url, stream=True, timeout=(10, 120)) as r:
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
    دالة متزامنة تستدعي yt-dlp وتحاول تنزيل ملف محلياً.
    - تحاول الصيغة المحددة أولاً إن وُجدت، ثم تجرب قائمة مرنة من البدائل.
    - بعد التحميل، تحاول إيجاد الملف النهائي وإرجاع المسار.
    - إن عاد yt-dlp بمصدر HLS (.m3u8) فقط، نحاول تحويله عبر ffmpeg.
    """
    try:
        base_opts = get_ytdlp_base_opts(verbose=verbose)

        # قائمة صيغ محاولات مصممة لتغطية معظم الحالات
        candidates = []
        if fmt:
            candidates.append(fmt)
        # صيغة صوت عامة، وصيغ فيديو تفضيلية تضمن امتداد mp4 إن أمكن
        candidates.extend([
            "bestaudio[ext=m4a]/bestaudio/best",
            "bestaudio/best",
            "bestvideo[ext=mp4]+bestaudio/best",
            "bestvideo[height<=1080]+bestaudio/best",
            "best"
        ])

        last_exc = None
        for candidate in candidates:
            opts = dict(base_opts)
            opts["format"] = candidate
            # لبعض الحالات نريد استخراج audio مباشرة (postprocessor)
            if candidate.startswith("bestaudio"):
                # نترك yt-dlp يتصرف لكن اذا احتجنا تحويل لاحقاً سنعالجه
                pass

            try:
                with YoutubeDL(opts) as ydl:
                    # نطلب تنزيل مباشر (download=True) لنتأكد من وجود ملف محلي
                    info = ydl.extract_info(link, download=True)
                    # حاول إيجاد الملف الناتج مباشرة
                    final = _info_to_final_path(info)
                    if final and os.path.exists(final):
                        return final

                    # بعض الأحيان yt-dlp يعطينا url للـ m3u8 أو ملف خارجي بدل تنزيل ملف
                    # حاول اكتشاف ذلك وتجربة تحويله عبر ffmpeg
                    url = None
                    if isinstance(info, dict):
                        # طلب URL الصريح إن وُجد
                        url = info.get("url") or info.get("requested_downloads", [{}])[0].get("url")
                        # طالما يوجد playlist entries، قد يحدث لدينا info['entries']
                        if not url and info.get("entries"):
                            # أحاول أول إدخال
                            entry = info["entries"][0] if info["entries"] else {}
                            url = entry.get("url") if isinstance(entry, dict) else None

                    if url and _is_m3u8_url(url):
                        # نحاول تحويل m3u8 إلى mp4 محلي
                        vid = info.get("id") or _safe_filename("video")
                        out_path = os.path.join(DOWNLOAD_DIR, f"{vid}.mp4")
                        ok = _run_ffmpeg_convert(url, out_path)
                        if ok:
                            return out_path

                    # بعض الأحيان yt-dlp يسمح بتحميل الوسائط كروابط منفصلة، نجرب تنزيل الرابط المباشر
                    if url and url.startswith("http"):
                        vid = info.get("id") or _safe_filename("direct")
                        ext = url.split("?")[0].split(".")[-1][:4]
                        out_path = os.path.join(DOWNLOAD_DIR, f"{vid}.{ext}")
                        # use requests blocking helper in executor
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

        # نهاية المحاولات
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
    تحميل عبر aiohttp (غير محظور).
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
                status = str(data.get("status","")).lower()
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
                status = str(data.get("status","")).lower()
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
    # سباق بين نتيجتين، نأخذ الأولى الصالحة
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
                # الغي الباقي
                for p in pending:
                    p.cancel()
                return result
        except Exception:
            pass
    # إن لم تنجح أي من أول الدوال، ننتظر البقية ونرجع أول نتيجة صحيحة
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
    الواجهة العامة: link (URL أو ID)، type in ("audio","video")
    تُعيد مسار الملف المحفوظ محليًا أو None
    """
    loop = asyncio.get_running_loop()
    vid = extract_video_id(link)

    # تحقق من الكاش أولاً
    if cached := find_cached_file(vid):
        if title:
            LOGGER.info(f"Track '{title}' - Served from cache")
        return cached

    if type == "audio":
        key = f"audio:{vid}"

        async def run():
            # مهمة yt-dlp في executor
            yt = asyncio.create_task(
                run_with_semaphore(
                    loop.run_in_executor(None, download_with_ytdlp_sync, link, "bestaudio/best", False)
                )
            )
            api = asyncio.create_task(api_download_audio(link)) if USE_AUDIO_API else None
            return await race_tasks(yt, api, title or "Unknown")

        return await deduplicate_download(key, run)

    if type == "video":
        key = f"video:{vid}"

        async def run():
            # نُجبر yt-dlp على تنزيل ملف MP4 إن أمكن (لا نُعطي م3u8 للـ player)
            # صيغة مرنة تحاول mp4 أولًا ثم fallback
            fmt = "bestvideo[ext=mp4][height<=1080]+bestaudio/best[ext=mp4]/best[ext=mp4]/best"
            yt = asyncio.create_task(
                run_with_semaphore(
                    loop.run_in_executor(None, download_with_ytdlp_sync, link, fmt, False)
                )
            )
            api = asyncio.create_task(api_download_video(link)) if USE_VIDEO_API else None
            return await race_tasks(yt, api, title or "Unknown")

        return await deduplicate_download(key, run)

    return None
