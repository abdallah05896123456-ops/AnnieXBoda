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
from typing import Dict, Optional, List

import aiofiles
import aiohttp
from aiohttp import TCPConnector
from yt_dlp import YoutubeDL

# --- Imports from AnnieXMedia Project Structure ---
# تأكد من أن هذه المسارات صحيحة في مشروعك
from AnnieXMedia.core.dir import CACHE_DIR, DOWNLOAD_DIR
from AnnieXMedia.utils.cookie_handler import COOKIE_PATH as _COOKIES_FILE
from AnnieXMedia.utils.tuning import CHUNK_SIZE, SEM
from config import API_KEY, API_URL, VIDEO_API_URL
from AnnieXMedia.logging import LOGGER

# Access global db to avoid deleting files in-use
# يفترض أن _GLOBAL_DB قاموس يحتوي على قوائم التشغيل الحالية
from AnnieXMedia.misc import db as _GLOBAL_DB

LOGGER = LOGGER(__name__)

# تفعيل الـ APIs فقط إذا كانت المفاتيح موجودة
USE_AUDIO_API = bool(API_URL and API_KEY)
USE_VIDEO_API = bool(VIDEO_API_URL and API_KEY)

# إدارة التحميلات الجارية لمنع التكرار
_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()

# جلسة HTTP مشتركة
_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()

YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")

# الكشف عن aria2 مرة واحدة عند البدء
ARIA2_PATH = shutil.which("aria2c")

# ---------------- directories & naming ----------------
# إعداد المجلدات
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
        # Fallback if lock fails strictly
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
        # نسخ القاموس لتجنب أخطاء التعديل أثناء الدوران
        for k, q in list(_GLOBAL_DB.items()):
            if not q:
                continue
            for item in q:
                if not isinstance(item, dict):
                    continue
                # فحص المسار العادي ومسار السرعة (إذا وجد)
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
    LOGGER.info("Cache cleaner loop started.")
    try:
        while True:
            now = time.time()
            to_delete = []
            async with _cache_lock:
                for p, expiry in list(_cache_registry.items()):
                    if expiry <= now:
                        # حذف الملف فقط إذا انتهى وقته ولم يعد مستخدماً
                        if not _is_file_in_use(p) and os.path.exists(p):
                            to_delete.append(p)
                        else:
                            # تجديد المهلة إذا كان لا يزال قيد الاستخدام
                            _cache_registry[p] = now + CACHE_TTL
            
            for p in to_delete:
                try:
                    os.remove(p)
                    LOGGER.info(f"cache_cleaner: removed expired file {p}")
                except Exception as e:
                    LOGGER.debug(f"cache_cleaner: failed to remove {p}: {e}")
                
                # تنظيف السجل
                async with _cache_lock:
                    _cache_registry.pop(p, None)
            
            await asyncio.sleep(30)
    except asyncio.CancelledError:
        LOGGER.info("Cache cleaner loop cancelled.")
        return
    except Exception as e:
        LOGGER.exception(f"cache_cleaner fatal error: {e}")


def init_cache_cleaner() -> None:
    """
    Start the background cleaner if event loop is running.
    Call this once during application startup.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_cache_cleaner_loop())
            LOGGER.debug("init_cache_cleaner: started")
        else:
            LOGGER.warning("init_cache_cleaner: event loop not running; cleaner not started")
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
    try:
        s = html.unescape(title)
        s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
        s = re.sub(r"\s+", "_", s.strip())
        s = s[:50] # Limit length
    except Exception:
        s = ""
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
        try:
            return s.split("v=")[-1].split("&")[0]
        except IndexError:
            pass
    if "youtu.be" in s:
        try:
            return s.split("/")[-1].split("?")[0]
        except IndexError:
            pass
    # Fallback for simple ID at end of URL
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
    
    # تحديد مجلد البحث الأساسي
    if kind == "audio":
        search_dirs = [AUDIO_DIR]
    elif kind == "video":
        search_dirs = [VIDEO_DIR]
    else:
        search_dirs = [AUDIO_DIR, VIDEO_DIR]

    # 1. البحث المحدد بالنوع (الأسلوب الجديد)
    if kind in ("audio", "video"):
        for d in search_dirs:
            # البحث عن الملفات التي تبدأ بـ ID وتحتوي على نوع الملف
            # النمط: ID_KIND_TITLE.EXT
            for ext in ("mp3", "m4a", "mp4", "mkv", "webm", "opus"):
                p = os.path.join(d, f"{video_id}_{kind}*.{ext}")
                matches = glob.glob(p)
                if matches:
                    # الأحدث أولاً
                    matches = sorted(matches, key=os.path.getmtime, reverse=True)
                    _register_cache_from_thread(matches[0])
                    return matches[0]
            
            # محاولة أوسع: أي ملف يبدأ بالآيدي في المجلد المحدد
            matches_any = glob.glob(os.path.join(d, f"{video_id}_*"))
            if matches_any:
                matches_any = sorted(matches_any, key=os.path.getmtime, reverse=True)
                for m in matches_any:
                    # تأكد أنه ملف وسائط وليس ملف مؤقت
                    if m.split('.')[-1].lower() in ["mp3", "m4a", "mp4", "mkv", "webm", "opus"]:
                        _register_cache_from_thread(m)
                        return m

    # 2. بحث شامل في كل المجلدات (Fallback)
    all_matches = []
    for d in [AUDIO_DIR, VIDEO_DIR]:
        all_matches.extend(glob.glob(os.path.join(d, f"{video_id}_*")))
    
    if all_matches:
        # استبعاد ملفات غير الوسائط
        media_matches = [m for m in all_matches if m.split('.')[-1].lower() in ["mp4", "mkv", "webm", "m4a", "mp3", "opus"]]
        if media_matches:
            best = sorted(media_matches, key=os.path.getmtime, reverse=True)[0]
            _register_cache_from_thread(best)
            return best

    # 3. Legacy fallback (النظام القديم في الجذر)
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
    Avoid enabling external_downloader for HLS/googlevideo links generally here.
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
        "socket_timeout": 15,
        "cachedir": str(CACHE_DIR),
        "ignoreerrors": True,
        "merge_output_format": "mp4",
        "nocheckcertificate": True,
        "geo_bypass": True,
        "postprocessors": [], # يمكن إضافة metadata هنا مستقبلاً
        "recodevideo": None,
        "nopostoverwrites": True,
        "prefer_ffmpeg": True,
    }

    if cookie := get_cookie_file():
        opts["cookiefile"] = cookie

    # يتم إضافة aria2 لاحقاً بناءً على نوع الرابط لتجنب المشاكل
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
    
    # 1. Check filename from info directly
    if info.get("_filename") and os.path.exists(info["_filename"]):
        return info["_filename"]

    # 2. Construct probable names
    ext = info.get("ext")
    if ext:
        # try common names
        cand1 = os.path.join(out_dir, f"{vid}.{ext}")
        if os.path.exists(cand1):
            return cand1
        cand2 = os.path.join(out_dir, f"{vid}_{kind}.{ext}")
        if os.path.exists(cand2):
            return cand2
    
    # 3. Fallback: scan dir for ID match
    matches = sorted(glob.glob(os.path.join(out_dir, f"{vid}*")), key=os.path.getmtime, reverse=True)
    for m in matches:
        if m.endswith(".part") or m.endswith(".ytdl"):
            continue
        return m
        
    return None


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
        # استخدام shlex.split غير مناسب هنا لأننا نستخدم shell=True للسهولة مع المعاملات المعقدة
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if proc.returncode == 0:
            LOGGER.debug(f"ffmpeg success. Cmd start: {cmd[:50]}...")
            return True
        stderr = (proc.stderr or "").strip().splitlines()
        head = "\n".join(stderr[:10])
        LOGGER.warning(f"ffmpeg failed (rc={proc.returncode}). stderr head:\n{head}")
        return False
    except subprocess.TimeoutExpired:
        LOGGER.warning(f"ffmpeg command timed out after {timeout}s")
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
        # 1. Copy attempt (Fastest)
        # نستخدم -bsf:a aac_adtstoasc لضمان توافق حاوية mp4 مع تدفقات aac
        cmd_copy = (
            f'ffmpeg -y -hide_banner -loglevel error '
            f'-fflags +nobuffer -flags low_delay -probesize 32 -analyzeduration 0 '
            f'-threads 0 -i {shlex.quote(input_src)} -c copy -bsf:a aac_adtstoasc {shlex.quote(out_path)}'
        )
        ok = _ffmpeg_run_capture(cmd_copy, timeout=600)
        if ok and os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
            _register_cache_from_thread(out_path)
            return True

        # 2. Re-encode attempt (More compatible)
        _, ext = os.path.splitext(out_path)
        ext = ext.lower().lstrip(".")
        
        # إعدادات التشفير بناءً على الامتداد
        if ext in ("mp4", "mkv", "webm"):
            cmd_recode = (
                f'ffmpeg -y -hide_banner -loglevel error '
                f'-fflags +nobuffer -flags low_delay -probesize 32 -analyzeduration 0 '
                f'-threads 0 -i {shlex.quote(input_src)} '
                f'-c:v libx264 -preset veryfast -crf 26 -c:a aac -b:a 128k -ac 2 '
                f'{shlex.quote(out_path)}'
            )
        elif ext == "opus":
             cmd_recode = (
                f'ffmpeg -y -hide_banner -loglevel error '
                f'-i {shlex.quote(input_src)} -c:a libopus -b:a 128k -ac 2 {shlex.quote(out_path)}'
            )
        else:
            # Default audio (aac/m4a/mp3)
            cmd_recode = (
                f'ffmpeg -y -hide_banner -loglevel error '
                f'-i {shlex.quote(input_src)} -c:a aac -b:a 128k -ac 2 {shlex.quote(out_path)}'
            )

        LOGGER.debug(f"ffmpeg copy failed, trying recode for {input_src}")
        ok2 = _ffmpeg_run_capture(cmd_recode, timeout=900)
        if ok2 and os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
            _register_cache_from_thread(out_path)
            return True
            
        LOGGER.debug(f"_run_ffmpeg_convert: all conversion attempts failed for {input_src}")
        return False
    except Exception as e:
        LOGGER.exception(f"ffmpeg conversion fatal: {e}")
        return False


def _download_http_blocking(url: str, out_path: str, chunk_size: int = CHUNK_SIZE) -> bool:
    """
    Blocking HTTP download helper (used in executor) for direct URLs.
    """
    try:
        import requests
        # Timeout: (connect, read)
        with requests.get(url, stream=True, timeout=(10, 180)) as r:
            r.raise_for_status()
            with open(out_path, "wb") as fh:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        fh.write(chunk)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
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
        ext = ext.lstrip(".").lower()
        if not ext:
            ext = "mp4" if kind == "video" else "m4a"
            
        final_name = os.path.join(out_dir, f"{desired_vid}_{kind}_{safe}.{ext}")

        # Case 1: If candidate is manifest -> convert into final_name
        if candidate_path.lower().endswith(".m3u8"):
            LOGGER.info(f"Detected M3U8 file at {candidate_path}, converting to {final_name}...")
            # For HLS, usually we want mp4 container
            final_name_hls = os.path.splitext(final_name)[0] + ".mp4"
            ok = _run_ffmpeg_convert(candidate_path, final_name_hls)
            if ok:
                try:
                    os.remove(candidate_path)
                except Exception:
                    pass
                _register_cache_from_thread(final_name_hls)
                return final_name_hls
            return None

        # Case 2: Candidate is a regular file (move/copy if needed)
        # Avoid overwrite if source and dest are same
        if os.path.abspath(candidate_path) != os.path.abspath(final_name):
            try:
                shutil.move(candidate_path, final_name)
            except Exception:
                try:
                    shutil.copy(candidate_path, final_name)
                    os.remove(candidate_path)
                except Exception:
                    LOGGER.debug(f"_ensure_named_final: move/copy failed for {candidate_path} -> {final_name}")
                    return candidate_path # Return original if rename fails
        
        _register_cache_from_thread(final_name)
        return final_name if os.path.exists(final_name) else None
    except Exception as e:
        LOGGER.exception(f"_ensure_named_final exception: {e}")
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

        # Formats priority
        candidates = []
        if fmt:
            candidates.append(fmt)
        
        if kind == "audio":
            candidates.extend([
                "bestaudio[ext=m4a]/bestaudio/best",
                "best"
            ])
        else:
            candidates.extend([
                "bestvideo[ext=mp4][vcodec!=?vp9][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "bestvideo[height<=1080]+bestaudio/best",
                "best"
            ])

        last_exc = None
        desired_vid = extract_video_id(link) or _make_link_id(link)
        
        # 1. Check Cache
        existing = find_cached_file(desired_vid, kind=kind)
        if existing:
            LOGGER.info(f"Cache Hit for {desired_vid} ({kind})")
            _register_cache_from_thread(existing)
            return existing

        # 2. Iterate formats
        for candidate in candidates:
            opts = dict(base_opts)
            opts["format"] = candidate

            # Intelligent Aria2 Disabling
            # Disable external downloader for HLS or GoogleVideo to prevent 403 Forbidden / Slow speeds
            use_aria = False
            if ARIA2_PATH:
                is_manifest = _is_m3u8_url(link)
                is_gvideo = "googlevideo.com" in link or "manifest.googlevideo" in link
                if not (is_manifest or is_gvideo):
                    use_aria = True
            
            if use_aria:
                opts["external_downloader"] = "aria2c"
                opts["external_downloader_args"] = ["-x", "8", "-k", "1M", "--min-split-size=1M"]
            else:
                opts.pop("external_downloader", None)
                opts.pop("external_downloader_args", None)

            try:
                with YoutubeDL(opts) as ydl:
                    # A. Extract Info
                    info = ydl.extract_info(link, download=True)
                    
                    # B. Check produced file
                    reported = _info_to_final_path(info, kind=kind, out_dir=out_dir)
                    
                    # C. Rename/Convert to Final
                    if reported and os.path.exists(reported):
                        final = _ensure_named_final(reported, desired_vid, kind, title_hint)
                        if final:
                            return final

                    # D. Edge Case: Info contains URL but file wasn't downloaded by ytdl (e.g. direct link logic)
                    url = None
                    if isinstance(info, dict):
                        url = info.get("url")
                        if not url and info.get("requested_downloads"):
                             url = info["requested_downloads"][0].get("url")
                        if not url and info.get("entries"):
                            entry = info["entries"][0] if info["entries"] else {}
                            url = entry.get("url") if isinstance(entry, dict) else None

                    # If url is M3U8 -> Convert
                    if url and _is_m3u8_url(url):
                        target_ext = "mp4" # safer for hls
                        out_path = os.path.join(out_dir, f"{desired_vid}_{kind}_{_safe_title_for_filename(title_hint)}.{target_ext}")
                        LOGGER.debug(f"Converting remote manifest URL -> {out_path}")
                        ok = _run_ffmpeg_convert(url, out_path)
                        if ok:
                            return out_path

                    # If url is Direct HTTP -> Download manual
                    if url and url.startswith("http"):
                        # guess extension
                        ext_guess = "mp4"
                        if "audio" in kind: ext_guess = "m4a"
                        
                        out_path = os.path.join(out_dir, f"{desired_vid}_{kind}_{_safe_title_for_filename(title_hint)}.{ext_guess}")
                        
                        # Use requests download if yt-dlp failed to write file
                        if not (reported and os.path.exists(reported)):
                            ok = _download_http_blocking(url, out_path)
                            if ok:
                                return out_path

            except Exception as e:
                last_exc = e
                # Don't log full stack trace for format retry
                LOGGER.debug(f"yt-dlp format '{candidate}' failed: {e}")
                continue
            
            # If we reached here and succeeded in one format, break? 
            # Logic above returns if successful. If loop continues, it means failure.

        LOGGER.error(f"All yt-dlp attempts failed for {link}. Last error: {last_exc}")
        return None
    except Exception as e:
        LOGGER.exception("download_with_ytdlp_sync fatal crash")
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
        retries = 0
        # تجنب الحلقة اللانهائية باستخدام عداد
        while retries < 30: # 30 seconds max wait
            async with session.get(url) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                status = str(data.get("status", "")).lower()
                
                if status == "done":
                    fname = _safe_title_for_filename(data.get('title', title_hint))
                    ext = data.get('format', 'm4a')
                    out = os.path.join(AUDIO_DIR, f"{vid}_audio_{fname}.{ext}")
                    
                    dlink = data.get("link")
                    if dlink:
                        res = await download_file(dlink, out)
                        if res: return res
                    return None
                
                if status == "error":
                    return None
                
                # Still processing
                await asyncio.sleep(1)
                retries += 1
        return None
    except Exception as e:
        LOGGER.debug(f"api_download_audio error: {e}")
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
        retries = 0
        while retries < 40: # 40 seconds max wait
            async with session.get(url) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                status = str(data.get("status", "")).lower()
                
                if status == "done":
                    fname = _safe_title_for_filename(data.get('title', title_hint))
                    ext = data.get('format', 'mp4')
                    out = os.path.join(VIDEO_DIR, f"{vid}_video_{fname}.{ext}")
                    
                    dlink = data.get("link")
                    if dlink:
                        res = await download_file(dlink, out)
                        if res: return res
                    return None
                
                if status == "error":
                    return None
                
                await asyncio.sleep(1)
                retries += 1
        return None
    except Exception as e:
        LOGGER.debug(f"api_download_video error: {e}")
        return None


# ---------------- orchestration ----------------

async def run_with_semaphore(coro):
    """Run a coroutine ensuring we don't exceed global SEM limit."""
    async with SEM:
        return await coro


async def deduplicate_download(key: str, runner):
    """
    If a download for 'key' is already running, wait for it.
    Otherwise, start the 'runner' coroutine.
    """
    async with _inflight_lock:
        if fut := _inflight.get(key):
            LOGGER.info(f"deduplicate: joining existing download for {key}")
            try:
                return await asyncio.wait_for(fut, timeout=300)
            except asyncio.TimeoutError:
                LOGGER.warning(f"deduplicate: timed out waiting for {key}")
                return None
            except Exception:
                return None
        
        # Create new future
        fut = asyncio.get_running_loop().create_future()
        _inflight[key] = fut
    
    try:
        res = await runner()
        if not fut.done():
            fut.set_result(res)
        return res
    except Exception as e:
        if not fut.done():
            try:
                fut.set_exception(e)
            except: pass
        return None
    finally:
        async with _inflight_lock:
            _inflight.pop(key, None)


async def race_tasks(yt_task, api_task, title: str, kind: str) -> Optional[str]:
    """
    Race between yt-dlp (local) and API (remote).
    Returns the path of the first successful download.
    Cancels the loser.
    """
    tasks = {t for t in (yt_task, api_task) if t}
    if not tasks:
        return None
    
    # Wait for FIRST_COMPLETED
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    
    result = None
    
    # Check winners
    for t in done:
        try:
            res = t.result()
            if res and os.path.exists(res) and os.path.getsize(res) > 0:
                result = res
                src = "yt-dlp" if t is yt_task else "API"
                LOGGER.info(f"Race Won by {src} | Track: '{title[:20]}..' ({kind})")
                break
        except Exception as e:
            LOGGER.debug(f"Task failed in race: {e}")

    # If first task failed, wait for remaining
    if not result and pending:
        for p in pending:
            try:
                res = await p
                if res and os.path.exists(res) and os.path.getsize(res) > 0:
                    result = res
                    src = "yt-dlp" if p is yt_task else "API"
                    LOGGER.info(f"Race Won by {src} (Fallback) | Track: '{title[:20]}..' ({kind})")
                    break
            except Exception:
                pass
    
    # Cancel any still pending tasks if we have a result
    if result and pending:
        for p in pending:
            p.cancel()
            
    return result


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

    # A. Determine ID
    vid = extract_video_id(link)
    if not vid:
        # If strict ID missing, try extracting via yt-dlp quick info or hash
        # Only do expensive extraction if really needed, otherwise use hash
        if "youtube" in link or "youtu.be" in link:
             # Try light extraction
             pass 
        id_key = _make_link_id(link)
    else:
        id_key = vid

    # B. Cache Check
    # We use vid if available for cache lookup, else id_key
    lookup_id = vid if vid else id_key
    if cached := find_cached_file(lookup_id, kind=kind):
        LOGGER.info(f"Served from Cache: {os.path.basename(cached)}")
        await register_cache(cached)
        return cached

    # C. Prepare Runners
    if type == "audio":
        key = f"audio:{id_key}"

        async def run_audio():
            # yt-dlp task
            yt = asyncio.create_task(
                run_with_semaphore(
                    loop.run_in_executor(
                        None, 
                        download_with_ytdlp_sync, 
                        link, 
                        "bestaudio[ext=m4a]/bestaudio/best", 
                        False, 
                        "audio", 
                        title
                    )
                )
            )
            # api task
            api = asyncio.create_task(api_download_audio(link, title)) if USE_AUDIO_API else None
            return await race_tasks(yt, api, title or link, "audio")

        result = await deduplicate_download(key, run_audio)
        if result: await register_cache(result)
        return result

    if type == "video":
        key = f"video:{id_key}"

        async def run_video():
            # video formats: prioritize 1080p mp4
            fmt = "bestvideo[ext=mp4][vcodec!=?vp9][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            yt = asyncio.create_task(
                run_with_semaphore(
                    loop.run_in_executor(
                        None, 
                        download_with_ytdlp_sync, 
                        link, 
                        fmt, 
                        False, 
                        "video", 
                        title
                    )
                )
            )
            api = asyncio.create_task(api_download_video(link, title)) if USE_VIDEO_API else None
            return await race_tasks(yt, api, title or link, "video")
