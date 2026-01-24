# Authored By Certified Coders © 2025
# Optimized by TitanOS (Custom Cookie Path + Anti-Ban + Aria2 Max Speed)
# Fixed & Debugged for High-End Servers

import asyncio
import os
import re
import logging
import traceback  # عشان نصطاد الخطأ بالتفصيل
from typing import Union, List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
import time

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.aio import VideosSearch

# --- محاولة استيراد الإعدادات من البوت ---
try:
    from AnnieXMedia.utils.formatters import time_to_seconds
    from AnnieXMedia import LOGGER
except ImportError:
    logging.basicConfig(level=logging.ERROR)
    def LOGGER(name): return logging.getLogger(name)
    def time_to_seconds(t): return 0

# إخفاء إزعاج المكتبات
logging.getLogger("yt_dlp").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

# --- إعدادات النظام ---
class Config:
    DOWNLOAD_PATH = "downloads"
    # تأكد إن ملف الكوكيز موجود في المسار ده
    COOKIE_PATH = "AnnieXMedia/assets/cookies.txt"
    # بنستخدم عدد Threads عالي عشان سيرفرك قوي
    MAX_WORKERS = 16 

if not os.path.exists(Config.DOWNLOAD_PATH):
    os.makedirs(Config.DOWNLOAD_PATH)

# --- الكاش (للذاكرة) ---
_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()
YOUTUBE_META_TTL = 3600

# --- دوال المساعدة ---

def get_cookie_file():
    """التحقق من وجود الكوكيز بشكل صارم"""
    paths_to_check = [
        Config.COOKIE_PATH,
        "cookies.txt",
        "AnnieXMedia/cookies.txt",
        "assets/cookies.txt"
    ]
    for path in paths_to_check:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    return None

# --- الكلاس الرئيسي ---

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://www.youtube.com/playlist?list="
        self.pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)
        # التحقق من وجود Aria2c
        self.has_aria2 = os.system("which aria2c > /dev/null 2>&1") == 0

    # -----------------------------------------------------------------
    # 🔗 معالجة الروابط
    # -----------------------------------------------------------------
    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset: break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None if offset in (None,) else text[offset : offset + length]

    # -----------------------------------------------------------------
    # 🔍 البحث والمعلومات (معدل لتفادي الأخطاء)
    # -----------------------------------------------------------------
    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        link = link.split("&")[0]

        # 1. فحص الكاش
        async with _cache_lock:
            if link in _cache:
                ts, val = _cache[link]
                if time.time() - ts < YOUTUBE_META_TTL:
                    return val[0], val[1]

        # 2. البحث الفعلي
        try:
            # محاولة البحث باستخدام VideosSearch
            results = VideosSearch(link, limit=1)
            res = await results.next()
            
            if not res or not res.get("result"):
                # محاولة بديلة (Fallback) في حالة فشل المكتبة الأولى
                raise ValueError("VideosSearch returned empty")
                
            data = res["result"][0]
            
            track_details = {
                "title": data["title"],
                "link": data["link"],
                "vidid": data["id"],
                "duration_min": data["duration"],
                "thumb": data["thumbnails"][0]["url"].split("?")[0],
                "cookiefile": get_cookie_file(),
            }
            
            # 3. حفظ في الكاش
            async with _cache_lock:
                _cache[link] = (time.time(), (track_details, data["id"]))
            
            return track_details, data["id"]
        
        except Exception as e:
            # تسجيل الخطأ الصامت هنا عشان نعرف لو البحث فيه مشكلة
            # LOGGER(__name__).warning(f"Search failed for {link}: {e}")
            return {"title": "Unknown", "link": link, "vidid": "error", "duration_min": "0:00", "thumb": ""}, "error"

    async def details(self, link: str, videoid: Union[bool, str] = None):
        d, i = await self.track(link, videoid)
        if i == "error": return None
        return d["title"], d["duration_min"], time_to_seconds(d["duration_min"]), d["thumb"], i

    async def title(self, link: str, videoid: Union[bool, str] = None):
        d, _ = await self.track(link, videoid)
        return d.get("title")

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        d, _ = await self.track(link, videoid)
        return d.get("duration_min")

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        d, _ = await self.track(link, videoid)
        return d.get("thumb")

    # -----------------------------------------------------------------
    # 📥 المحرك النووي للتحميل (Titan Engine Optimized)
    # -----------------------------------------------------------------
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
    ) -> Tuple[Optional[str], bool]:
        
        # تصحيح الرابط لو جاي من زرار
        if videoid: 
            link = self.base + link
        
        # 🛡️ حماية ضد رابط الـ ID 0
        if "youtube.com/0" in link or link.endswith("="):
            LOGGER(__name__).error(f"❌ Blocked Invalid Link: {link}")
            return None, False

        loop = asyncio.get_running_loop()

        # استخراج ID للفيديو لتسمية الملف بشكل نظيف
        try:
            if "v=" in link: 
                vid_id = link.split("v=")[1].split("&")[0]
            elif "youtu.be/" in link:
                vid_id = link.split("youtu.be/")[1].split("?")[0]
            else: 
                vid_id = str(int(time.time()))
        except:
             vid_id = str(int(time.time()))

        # تحديد المسار
        file_name = f"{vid_id}.{'mp4' if video else 'm4a'}"
        final_path = os.path.join(Config.DOWNLOAD_PATH, file_name)

        # 🔥 إعدادات التحميل المعدلة للسرعة القصوى 🔥
        ydl_opts = {
            "outtmpl": final_path,
            "cookiefile": get_cookie_file(),
            "geo_bypass": True,
            "nocheckcertificate": True, # مهم جداً
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "overwrites": True,
            # استخدام عملاء متنوعين لتجاوز الحظر
            "extractor_args": {
                'youtube': {
                    'skip': ['dash', 'hls'],
                    'player_client': ['ios', 'android', 'web'], # ios حالياً الأقوى
                    'player_skip': ['configs', 'js'],
                }
            }
        }

        # تحديد الجودة
        if video:
            ydl_opts["format"] = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
        else:
            ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
        
        # 🚀 إعدادات Aria2 للسرعة الجنونية (بما إن عندك باندويث عالي)
        if self.has_aria2:
            ydl_opts["external_downloader"] = "aria2c"
            ydl_opts["external_downloader_args"] = [
                "-x", "16",  # 16 اتصالات لكل سيرفر
                "-s", "16",  # تقسيم الملف لـ 16 جزء
                "-k", "1M",  # حجم القطعة
                "--min-split-size", "1M",
                "--max-connection-per-server", "16"
            ]

        # دالة التنفيذ مع صائد الأخطاء
        def _run_download():
            if os.path.exists(final_path):
                return final_path
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([link])
            except Exception as e:
                # 📝 هنا هيطبعلك السبب الحقيقي في اللوج
                err_msg = traceback.format_exc()
                LOGGER(__name__).error(f"❌ Download Failed for {link}\nError: {e}\nTraceback: {err_msg}")
                return None
            
            if os.path.exists(final_path):
                return final_path
            return None

        # تشغيل التحميل
        downloaded_file = await loop.run_in_executor(self.pool, _run_download)
        
        if downloaded_file:
            return downloaded_file, True
        return None, False

    # -----------------------------------------------------------------
    # 📺 قوائم التشغيل والسلايدر
    # -----------------------------------------------------------------
    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid: link = self.listbase + link
        if "&" in link: link = link.split("&")[0]
        
        cmd = (
            f"yt-dlp -i --compat-options no-youtube-unavailable-videos "
            f"--get-id --flat-playlist --playlist-end {limit} --skip-download '{link}' "
            f"2>/dev/null"
        )
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        out, _ = await proc.communicate()
        
        try:
            result = [key for key in out.decode().split("\n") if key]
        except:
            result = []
        return result

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        
        ytdl_opts = {"quiet": True, "cookiefile": get_cookie_file()}
        with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
            formats_available = []
            try:
                r = ydl.extract_info(link, download=False)
                for format in r.get("formats", []):
                    if not format.get("filesize") and not format.get("filesize_approx"): continue
                    
                    formats_available.append({
                        "format": format["format"],
                        "filesize": format.get("filesize") or format.get("filesize_approx"),
                        "format_id": format["format_id"],
                        "ext": format["ext"],
                        "format_note": format.get("format_note", ""),
                        "yturl": link,
                    })
            except: pass
            
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        try:
            # تقليل الليمت هنا لتسريع الاستجابة
            a = VideosSearch(link, limit=5) 
            res = await a.next()
            if not res or not res.get("result"):
                return "Error", "0", "", "error"
                
            result = res.get("result")
            # التأكد من وجود نتائج كافية للـ index المطلوب
            if query_type >= len(result):
                r = result[0] # Fallback to first result
            else:
                r = result[query_type]
                
            return r["title"], r["duration"], r["thumbnails"][0]["url"].split("?")[0], r["id"]
        except Exception as e:
            LOGGER(__name__).error(f"Slider Error: {e}")
            return "Error", "0", "", "error"

# تصدير الكائن للاستخدام
YouTube = YouTubeAPI()
