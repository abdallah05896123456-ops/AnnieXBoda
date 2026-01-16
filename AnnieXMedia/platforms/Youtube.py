# Authored By Certified Coders © 2025
# THE UNIVERSE BEAST EDITION: Hybrid Search + Hyper-Threading Aria2c + Smart Caching + Anti-Block

import asyncio
import contextlib
import json
import os
import re
import time
import requests
import shutil
from typing import Dict, List, Optional, Tuple, Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch, Playlist

import config
from AnnieXMedia.utils.database import is_on_off
from AnnieXMedia.utils.errors import capture_internal_err
from AnnieXMedia.utils.formatters import time_to_seconds

# === Tuning & Defaults ===
try:
    from AnnieXMedia.utils.tuning import YTDLP_TIMEOUT, YOUTUBE_META_MAX, YOUTUBE_META_TTL
except ImportError:
    YTDLP_TIMEOUT = 300
    YOUTUBE_META_MAX = 10000
    YOUTUBE_META_TTL = 1200

# === Caching System (Memory Optimization) ===
_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()

# === Constants & Configs ===
COOKIE_FILE_NAME = "cookies.txt"
DOWNLOAD_DIR = "downloads"
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")

# تأكد من وجود مجلد التحميل
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# === 1. The Smart Cleaner (تنظيف تلقائي للمساحة) ===
def _clean_stale_files():
    now = time.time()
    ttl = 600  # حذف الملفات الأقدم من 10 دقائق
    try:
        for filename in os.listdir(DOWNLOAD_DIR):
            file_path = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.isfile(file_path):
                if os.stat(file_path).st_mtime < now - ttl:
                    os.remove(file_path)
    except Exception:
        pass

# === 2. Secure Cookie Loader (تحميل الكوكيز بذكاء) ===
def _download_cookies_from_secret():
    cookie_url = os.getenv("COOKIE_URL")
    if not cookie_url:
        return
    # لو الملف موجود وفيه داتا، متضيعش وقت
    if os.path.exists(COOKIE_FILE_NAME) and os.path.getsize(COOKIE_FILE_NAME) > 0:
        return
    try:
        response = requests.get(cookie_url, timeout=10)
        if response.status_code == 200:
            content = response.text
            if "# Netscape" in content or "# HTTP" in content:
                with open(COOKIE_FILE_NAME, "w") as f:
                    f.write(content)
            else:
                print("⚠️ Warning: Invalid Cookie Format detected!")
    except Exception:
        pass

_download_cookies_from_secret()
_clean_stale_files()

# === Helpers ===
def _cookiefile_path() -> Optional[str]:
    if os.path.exists(COOKIE_FILE_NAME) and os.path.getsize(COOKIE_FILE_NAME) > 0:
        return COOKIE_FILE_NAME
    return None

def _cookies_args() -> List[str]:
    path = _cookiefile_path()
    return ["--cookies", path] if path else []

async def _exec_proc(*args: str) -> Tuple[bytes, bytes]:
    """تنفيذ أوامر النظام بسرعة عالية"""
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

# === 3. Hybrid Search Engine (محرك البحث الهجين) ===
@capture_internal_err
async def cached_youtube_search(query: str) -> List[Dict]:
    key = f"q:{query}"
    now = time.time()

    # 1. Check RAM Cache (أسرع حاجة)
    async with _cache_lock:
        if key in _cache:
            ts, val = _cache[key]
            if now - ts < YOUTUBE_META_TTL:
                return val
            _cache.pop(key, None)
        if len(_cache) > YOUTUBE_META_MAX:
            _cache.clear()

    result = []
    # 2. Try New Library (دقيقة وسريعة)
    try:
        search = VideosSearch(query, limit=1)
        data = await search.next()
        result = data.get("result", [])
    except Exception:
        pass
    
    # 3. Cache & Return
    if result:
        async with _cache_lock:
            _cache[key] = (now, result)

    return result

# === MAIN CLASS ===
class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self._url_pattern = re.compile(r"(?:youtube\.com|youtu\.be)")
        # تنظيف دوري عند كل استدعاء
        _clean_stale_files()

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            link = self.base_url + videoid.strip()
        link = link.strip()
        if "youtu.be" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        return link.split("&")[0]

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

    # === Advanced Metadata ===
    @capture_internal_err
    async def details(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], int, str, str]:
        prepared_link = self._prepare_link(link, videoid)
        result = await cached_youtube_search(prepared_link)
        
        # Fallback: لو البحث فشل، جرب yt-dlp سريع
        if not result:
             try:
                 stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "--dump-json", "--no-warnings", prepared_link)
                 if stdout:
                     info = json.loads(stdout.decode())
                     return info.get("title", "Unknown"), info.get("duration_string"), info.get("duration", 0), info.get("thumbnail", ""), info.get("id", "")
             except:
                 pass
             return "Unknown", "00:00", 0, "", ""
            
        info = result[0]
        dt = info.get("duration")
        ds = int(time_to_seconds(dt)) if dt else 0
        thumb = (info.get("thumbnail") or (info.get("thumbnails") or [{}])[-1].get("url", "")).split("?")[0]
        return info.get("title", ""), dt, ds, thumb, info.get("id", "")

    @capture_internal_err
    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        t, _, _, _, _ = await self.details(link, videoid)
        return t

    @capture_internal_err
    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        _, d, _, _, _ = await self.details(link, videoid)
        return d

    @capture_internal_err
    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        _, _, _, t, _ = await self.details(link, videoid)
        return t

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        prepared_link = self._prepare_link(link, videoid)
        result = await cached_youtube_search(prepared_link)
        
        if not result:
            # Fallback قوي جداً
            stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "--dump-json", "--no-warnings", prepared_link)
            if stdout:
                try:
                    info = json.loads(stdout.decode())
                    return {
                        "title": info.get("title", ""),
                        "link": info.get("webpage_url", prepared_link),
                        "vidid": info.get("id", ""),
                        "duration_min": info.get("duration_string", "00:00"),
                        "thumb": info.get("thumbnail", ""),
                    }, info.get("id", "")
                except:
                    pass
            return {}, ""

        info = result[0]
        thumb = (info.get("thumbnail") or (info.get("thumbnails") or [{}])[-1].get("url", "")).split("?")[0]
        details = {
            "title": info.get("title", ""),
            "link": info.get("link", prepared_link),
            "vidid": info.get("id", ""),
            "duration_min": info.get("duration"),
            "thumb": thumb,
        }
        return details, info.get("id", "")

    # === 🔥 HYPER-THREADING DOWNLOAD ENGINE 🔥 ===
    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None, 
        songvideo: Union[bool, str] = None, 
        format_id: Union[bool, str] = None, 
        title: Union[bool, str] = None,     
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None], str]:
        
        link = self._prepare_link(link, videoid)
        loop = asyncio.get_running_loop()

        # 1. Quality Control System (نظام الجودة الديناميكي)
        sys_quality = getattr(config, "SYSTEM_QUALITY", "high").lower()
        
        if sys_quality == "low":
            vid_fmt = "bestvideo[height<=360]+bestaudio[abr<=64]/best[height<=360]"
        elif sys_quality == "medium":
            vid_fmt = "bestvideo[height<=480]+bestaudio[abr<=96]/best[height<=480]"
        else:
            # High (Default)
            vid_fmt = "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]"

        aud_fmt = "bestaudio[ext=m4a]/bestaudio/best"

        # 2. Aria2c Hyper-Threading Config (محرك السرعة)
        # -x 16: 16 connections per server
        # -s 16: Split file into 16 parts
        # -j 16: 16 parallel downloads
        # -k 1M: Min split size 1MB (Force split)
        aria_args = {
            'external_downloader': 'aria2c',
            'external_downloader_args': ['-x', '16', '-s', '16', '-j', '16', '-k', '1M']
        }
        
        cookie_path = _cookiefile_path()

        def _run_download(opts):
            # استخدام Download Folder لتنظيم الملفات
            with yt_dlp.YoutubeDL(opts) as ydl:
                try:
                    info = ydl.extract_info(link, download=False)
                    filename = ydl.prepare_filename(info)
                    # لو الملف موجود مسبقاً، رجعه فوراً (Super Cache)
                    if os.path.exists(filename):
                        return filename
                    ydl.download([link])
                    return filename
                except Exception as e:
                    print(f"Download Error: {e}")
                    return None

        # 3. Execution Logic
        if songvideo:
            # Song Video (Alexa Mode)
            opts = {
                "format": f"{format_id}+140" if format_id else vid_fmt,
                "outtmpl": f"{DOWNLOAD_DIR}/{title}.%(ext)s" if title else f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "merge_output_format": "mp4",
                **aria_args
            }
            if cookie_path: opts["cookiefile"] = cookie_path
            return await loop.run_in_executor(None, _run_download, opts)

        elif songaudio:
            # Song Audio (Alexa Mode)
            opts = {
                "format": format_id if format_id else aud_fmt,
                "outtmpl": f"{DOWNLOAD_DIR}/{title}.%(ext)s" if title else f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
                **aria_args
            }
            if cookie_path: opts["cookiefile"] = cookie_path
            return await loop.run_in_executor(None, _run_download, opts)

        elif video:
            # Bot Stream Video (Force Download to fix Block)
            opts = {
                "format": vid_fmt,
                "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                **aria_args
            }
            if cookie_path: opts["cookiefile"] = cookie_path
            fpath = await loop.run_in_executor(None, _run_download, opts)
            # نرجع True دايماً عشان البوت يفهمه كملف محلي
            return (fpath, True) if fpath else (None, None)

        else:
            # Bot Stream Audio (Force Download to fix Block)
            opts = {
                "format": aud_fmt,
                "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                **aria_args
            }
            if cookie_path: opts["cookiefile"] = cookie_path
            fpath = await loop.run_in_executor(None, _run_download, opts)
            return (fpath, True) if fpath else (None, None)

    # === Playlist & Utils ===
    @capture_internal_err
    async def playlist(self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None) -> List[str]:
        if videoid: link = self.playlist_url + str(videoid)
        link = self._prepare_link(link).split("&")[0]

        try:
            plist = await Playlist.get(link)
            videos = plist.get("videos", [])
            items = [v.get("id") for v in videos[:limit] if v.get("id")]
            if items: return items
        except Exception:
            pass

        stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "-i", "--get-id", "--flat-playlist", "--playlist-end", str(limit), "--skip-download", link)
        items = stdout.decode().strip().split("\n") if stdout else []
        return [i for i in items if i]

    @capture_internal_err
    async def formats(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        opts = {"quiet": True}
        if cf := _cookiefile_path(): opts["cookiefile"] = cf
        out: List[Dict] = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                for fmt in info.get("formats", []):
                    if "dash" in str(fmt.get("format", "")).lower(): continue
                    if not fmt.get("filesize") and not fmt.get("filesize_approx"): continue
                    out.append({
                        "format": fmt["format"],
                        "filesize": fmt.get("filesize") or fmt.get("filesize_approx"),
                        "format_id": fmt["format_id"],
                        "ext": fmt["ext"],
                        "format_note": fmt.get("format_note", ""),
                        "yturl": link,
                    })
        except Exception:
            pass
        return out, link

    @capture_internal_err
    async def slider(self, link: str, query_type: int, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], str, str]:
        prepared = self._prepare_link(link, videoid)
        data = await VideosSearch(prepared, limit=10).next()
        results = data.get("result", [])
        if not results or query_type >= len(results): return "", "00:00", "", ""
        r = results[query_type]
        return (r.get("title", ""), r.get("duration"), r.get("thumbnails", [{}])[-1].get("url", "").split("?")[0], r.get("id", ""))
