# Authored By Certified Coders © 2026
# TITANIUM GOD MODE: ULTRA FAST DOWNLOADER
# MODEL: SAMSUNG GALAXY S25 ULTRA (5G+) SPOOFING
# NETWORK: 6G READY | 2.6Gbps OPTIMIZED | NO STREAM-WHILE-DOWNLOADING

import asyncio
import json
import logging
import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple, Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.aio import Playlist, VideosSearch

# --- استيراد الأدوات المساعدة مع حماية من الأخطاء ---
try:
    from AnnieXMedia.utils.cookie_handler import COOKIE_PATH
except ImportError:
    COOKIE_PATH = None

try:
    from AnnieXMedia.utils.formatters import time_to_seconds
except ImportError:
    def time_to_seconds(x): return 0

try:
    from AnnieXMedia.utils.database import is_on_off
except ImportError:
    async def is_on_off(x): return False

try:
    from AnnieXMedia.utils.downloader import yt_dlp_download
except ImportError:
    yt_dlp_download = None

# --- إعدادات اللوج ---
logging.getLogger("yt_dlp").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
LOG = logging.getLogger("TitanYouTube_2026")

# --- تهيئة المسارات والهاردوير ---
DOWNLOAD_DIR = os.path.abspath(os.path.join(os.getcwd(), "downloads"))
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# استخدام 64 مسار للمعالجة (يستغل الـ 16 vCPU بالكامل)
POOL = ThreadPoolExecutor(max_workers=64)

# --- إعدادات Aria2c (وضع السرعة القصوى 2026) ---
HAS_ARIA2 = shutil.which("aria2c") is not None
ARIA2_ARGS = [
    "-c", 
    "-x", "16",           # 16 خط اتصال لكل سيرفر
    "-s", "16",           # تقسيم الملف لـ 16 جزء
    "-j", "32",           # 32 تحميل متوازي
    "-k", "1M",           # حجم التقسيم الأدنى
    "--file-allocation=none", # تخصيص فوري (بدون انتظار حجز مساحة)
    "--buffer-size=2048M",    # استخدام 2 جيجا رام كاش (لتفادي عنق زجاجة الهارد)
    "--quiet=true",
    "--max-tries=3",          # محاولات قليلة لأن النت قوي
    "--connect-timeout=2"
]

# --- إعدادات الكاش والبحث ---
_meta_cache: Dict[str, Tuple[float, Dict]] = {}
_meta_lock = asyncio.Lock()
YOUTUBE_META_TTL = 3600
YOUTUBE_ID_RE = re.compile(r"(?:v=|\/)([A-Za-z0-9_-]{11})")


# --- دوال مساعدة ---

def get_cookie_path() -> Optional[str]:
    """تحديد مسار الكوكيز بدقة"""
    paths = [
        os.path.join(os.getcwd(), "AnnieXMedia", "assets", "cookies.txt"),
        os.path.join(os.getcwd(), "cookies.txt"),
        str(COOKIE_PATH) if COOKIE_PATH else ""
    ]
    for p in paths:
        if p and os.path.exists(p) and os.path.getsize(p) > 0:
            return p
    return None

def extract_video_id(link: str) -> str:
    if not link: return ""
    m = YOUTUBE_ID_RE.search(link)
    if m: return m.group(1)
    return link.split("/")[-1].split("?")[0]

def get_base_opts() -> Dict:
    opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "continuedl": True,
        "noprogress": True,
        "ignoreerrors": True,
        "force_ip_v4": True,           # ⚡ إجباري للسرعة وتفادي التايم أوت
        "check_formats": False,        # إلغاء الفحص لتسريع البدء
        "youtube_include_dash_manifest": False,
        "geo_bypass": True,
    }
    if HAS_ARIA2:
        opts["external_downloader"] = "aria2c"
        opts["external_downloader_args"] = ARIA2_ARGS
    
    if cookie := get_cookie_path():
        opts["cookiefile"] = cookie
    return opts


# ==============================================================================
# الكلاس الرئيسي: YouTube API (2026 Optimized)
# ==============================================================================

class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self.pool = POOL
        LOG.info(f"🚀 TitanEngine 2026 Started. Spoofing: S25 Ultra. Net: 2.6Gbps Mode.")

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            return self.base_url + videoid.strip()
        link = (link or "").strip()
        if "youtu.be" in link:
            return self.base_url + link.split("/")[-1].split("?")[0]
        if "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            return self.base_url + link.split("/")[-1].split("?")[0]
        return link.split("&")[0]

    # --------------------------------------------------------------------------
    # التحقق واستخراج الروابط
    # --------------------------------------------------------------------------
    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        return bool(re.search(r"(?:youtube\.com|youtu\.be)", self._prepare_link(link, videoid)))

    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            if not msg: continue
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset: ent.offset + ent.length].split("&si")[0]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url.split("&si")[0]
        return None

    # --------------------------------------------------------------------------
    # جلب المعلومات (Metadata System)
    # --------------------------------------------------------------------------
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        prepared = self._prepare_link(link, videoid)
        
        # 1. البحث في الكاش
        async with _meta_lock:
            if prepared in _meta_cache:
                ts, val = _meta_cache[prepared]
                if time.time() - ts < YOUTUBE_META_TTL:
                    return val
        
        # 2. البحث السريع
        try:
            data = await VideosSearch(prepared, limit=1).next()
            info = data["result"][0]
            details = {
                "title": info.get("title", "Unknown"),
                "link": prepared,
                "vidid": info.get("id", ""),
                "duration_min": info.get("duration", "0:00"),
                "thumb": (info.get("thumbnails", [{}])[-1].get("url", "")).split("?")[0],
                "channel": info.get("channel", {}).get("name", "Unknown"),
            }
            async with _meta_lock:
                _meta_cache[prepared] = (time.time(), (details, info.get("id", "")))
            return details, info.get("id", "")
        except Exception:
            pass

        return {"title": "Unknown", "link": prepared, "vidid": "error", "duration_min": "0:00", "thumb": ""}, "error"

    async def details(self, link: str, videoid: Union[str, bool, None] = None):
        d, vid = await self.track(link, videoid)
        if vid == "error": return None
        return d["title"], d["duration_min"], time_to_seconds(d["duration_min"]), d["thumb"], vid

    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        d, _ = await self.track(link, videoid)
        return d.get("title", "")

    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        d, _ = await self.track(link, videoid)
        return d.get("duration_min")

    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        d, _ = await self.track(link, videoid)
        return d.get("thumb", "")

    # --------------------------------------------------------------------------
    # 🚀 محرك التحميل (SAMSUNG S25 ULTRA 5G MODE)
    # --------------------------------------------------------------------------
    async def _download_internal(self, link: str, video: bool = False, format_id: str = None) -> Optional[str]:
        """
        محرك التحميل الداخلي:
        - تم إزالة البث الفوري (عشان الاستقرار).
        - بيستغل سرعة 2.6Gbps كاملة.
        - بينتحل شخصية S25 Ultra لجلب أعلى باندويدث من يوتيوب.
        """
        prepared = self._prepare_link(link)
        vid = extract_video_id(prepared) or str(int(time.time()))
        loop = asyncio.get_running_loop()

        # فحص وجود الملف مسبقاً (كاش)
        for fname in os.listdir(DOWNLOAD_DIR):
            if fname.startswith(vid) and not fname.endswith(".aria2"):
                return os.path.join(DOWNLOAD_DIR, fname)

        opts = get_base_opts()
        
        # إعدادات الصيغ (بدون تحويل للحفاظ على السرعة)
        if format_id:
            opts["format"] = format_id
        elif video:
            opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]"
            opts["merge_output_format"] = "mp4"
        else:
            opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"

        # 📱 SPOOFING: SAMSUNG GALAXY S25 ULTRA (Android 16)
        # هذا التمويه بيجبر يوتيوب يتعامل مع السيرفر كأنه موبايل 5G حديث
        opts["extractor_args"] = {"youtube": {"player_client": ["android", "web"]}}
        opts["http_headers"] = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 16; SM-S938B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Mode": "navigate",
        }

        # تشغيل التحميل (Full Speed Download)
        def _sync_dl():
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([prepared])
                    info = ydl.extract_info(prepared, download=False)
                    final_path = os.path.join(DOWNLOAD_DIR, f"{info['id']}.{info['ext']}")
                    # التأكد إن الملف نزل فعلاً
                    if os.path.exists(final_path):
                        return final_path
                    return None
            except Exception as e:
                LOG.error(f"Download Error: {e}")
                return None

        # تشغيل في الخلفية وانتظار الانتهاء
        # (تم إزالة خاصية البث أثناء التحميل لضمان استقرار الملف)
        return await loop.run_in_executor(self.pool, _sync_dl)

    # --------------------------------------------------------------------------
    # واجهة التحميل العامة
    # --------------------------------------------------------------------------
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        songaudio: bool = False,
        songvideo: bool = False,
        format_id: str = None,
        title: str = None
    ) -> Tuple[Optional[str], Optional[bool]]:
        
        prepared = self._prepare_link(link, videoid)

        # 1. محاولة البث المباشر (Direct URL) للفيديو فقط
        # عشان لو الفيديو طويل جداً ومش محتاج تحميل
        if video:
            try:
                cmd = ["yt-dlp", "--force-ipv4", "--dump-json", prepared]
                proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                out, _ = await proc.communicate()
                if out and json.loads(out).get("is_live"):
                    cmd_url = ["yt-dlp", "--force-ipv4", "-g", prepared]
                    proc_url = await asyncio.create_subprocess_exec(*cmd_url, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                    url_out, _ = await proc_url.communicate()
                    return url_out.decode().strip(), None
            except: pass

        # 2. دعم الدونلودر الخارجي (اختياري)
        try:
            if await is_on_off(1) and yt_dlp_download:
                p = await yt_dlp_download(prepared, type="video" if video else "audio", title=title or await self.title(prepared))
                return (p, True) if p else (None, None)
        except Exception:
            pass

        # 3. التحميل بمحرك S25 Ultra
        path = await self._download_internal(prepared, video=bool(video), format_id=format_id)
        
        if path:
            return path, True
        
        return None, None

    # --------------------------------------------------------------------------
    # الإضافات (Slider, Playlist, Formats, Video)
    # --------------------------------------------------------------------------
    async def slider(self, link: str, query_type: int, videoid: Union[str, bool, None] = None):
        try:
            data = await VideosSearch(self._prepare_link(link, videoid), limit=10).next()
            r = data["result"][query_type]
            return r["title"], r["duration"], r["thumbnails"][0]["url"].split("?")[0], r["id"]
        except: return "Error", "0", "", "error"

    async def playlist(self, link, limit, user_id, videoid: Union[str, bool, None] = None):
        if videoid: link = f"https://youtube.com/playlist?list={videoid}"
        cmd = ["yt-dlp", "--flat-playlist", "--get-id", "--playlist-end", str(limit), link]
        if cookie := get_cookie_path(): cmd[1:1] = ["--cookies", cookie]
        
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await proc.communicate()
        return out.decode().splitlines() if out else []

    async def formats(self, link: str, videoid: Union[str, bool, None] = None):
        prepared = self._prepare_link(link, videoid)
        def _get():
            try:
                with yt_dlp.YoutubeDL(get_base_opts()) as ydl:
                    r = ydl.extract_info(prepared, download=False)
                    return [{
                        "format": f["format"], "filesize": f.get("filesize") or f.get("filesize_approx"),
                        "format_id": f["format_id"], "ext": f["ext"], "format_note": f.get("format_note"), "yturl": prepared
                    } for f in r.get("formats", []) if f.get("filesize") or f.get("filesize_approx")]
            except: return []
        return await self.pool.submit(_get), prepared

    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        prepared = self._prepare_link(link, videoid)
        # S25 Ultra Spoofing for Direct URL as well
        cmd = ["yt-dlp", "--force-ipv4", "-g", "-f", "best[ext=mp4]/best", "--user-agent", "Mozilla/5.0 (Linux; Android 16; SM-S938B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Mobile Safari/537.36", prepared]
        if cookie := get_cookie_path(): cmd[1:1] = ["--cookies", cookie]
        
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            if stdout:
                return 1, stdout.decode().splitlines()[0]
            return 0, stderr.decode()
        except Exception as e:
            return 0, str(e)

# تصدير الكائن النهائي
YouTube = YouTubeAPI()
