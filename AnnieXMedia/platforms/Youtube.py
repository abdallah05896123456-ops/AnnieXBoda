# Authored By Certified Coders © 2025
# Optimized by TitanOS (Hybrid Engine: Aria2 + Native + Client Spoofing)

import asyncio
import os
import re
import json
import time
import random
import logging
from typing import Union, List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.aio import VideosSearch, Playlist

# --- محاولة استيراد الإعدادات من البوت ---
try:
    from AnnieXMedia.utils.database import is_on_off
    from AnnieXMedia.utils.formatters import time_to_seconds
    from AnnieXMedia import LOGGER
except ImportError:
    # Fallback لو الملفات مش موجودة عشان الكود ميكسرش
    logging.basicConfig(level=logging.ERROR)
    def LOGGER(name): return logging.getLogger(name)
    async def is_on_off(x): return True
    def time_to_seconds(t): return 0

# إخفاء إزعاج المكتبات
logging.getLogger("yt_dlp").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

# --- إعدادات النظام ---
class Config:
    DOWNLOAD_PATH = "downloads"
    MAX_WORKERS = 10

if not os.path.exists(Config.DOWNLOAD_PATH):
    os.makedirs(Config.DOWNLOAD_PATH)

# --- الكاش (للذاكرة) ---
_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()
YOUTUBE_META_TTL = 3600

# --- دوال المساعدة ---

def get_cookie_file():
    """نظام ذكي لاختيار الكوكيز: ملف مباشر أو مجلد"""
    # 1. لو فيه ملف مباشر
    if os.path.exists("cookies.txt") and os.path.getsize("cookies.txt") > 0:
        return "cookies.txt"
    # 2. لو فيه فولدر كوكيز (زي AnonX)
    if os.path.exists("cookies"):
        files = [f for f in os.listdir("cookies") if f.endswith(".txt")]
        if files:
            return os.path.join("cookies", random.choice(files))
    # 3. لو مفيش (البوت هيحاول يشتغل من غير كوكيز مع Spoofing)
    return None

def get_user_agent():
    """توليد User-Agent عشوائي للتمويه"""
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
        "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36",
    ]
    return random.choice(agents)

# --- الكلاس الرئيسي ---

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="
        self.pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)
        
        # التأكد من وجود Aria2 (اختياري)
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
    # 🔍 البحث والمعلومات (مع الكاش)
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
            results = VideosSearch(link, limit=1)
            res = await results.next()
            if not res or not res.get("result"):
                raise ValueError("No Result")
                
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
        except Exception:
            return {"title": "Unknown", "link": link, "vidid": "error", "duration_min": "0:00", "thumb": ""}, "error"

    # دوال مساعدة لجلب التفاصيل
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
    # 📥 المحرك النووي للتحميل (Titan Engine)
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
        
        if videoid: link = self.base + link
        loop = asyncio.get_running_loop()

        # استخراج ID للفيديو لتسمية الملف
        try:
            if "v=" in link: vid_id = link.split("v=")[1].split("&")[0]
            elif "youtu.be/" in link: vid_id = link.split("youtu.be/")[1].split("?")[0]
            else: vid_id = str(int(time.time()))
        except:
             vid_id = str(int(time.time()))

        # تحديد المسار
        file_name = f"{vid_id}.{'mp4' if video else 'm4a'}"
        final_path = os.path.join(Config.DOWNLOAD_PATH, file_name)

        # 🔥 إعدادات FFMPEG و Anti-Ban 🔥
        # هنا السحر: بنقول لليوتيوب إننا "موبايل أندرويد" عشان ميعملش Block
        extractor_args = {
            'youtube': {
                'skip': ['dash', 'hls'],
                'player_client': ['android', 'web'], # الترتيب مهم: أندرويد الأول
            }
        }

        # إعدادات عامة للتحميل
        base_opts = {
            "outtmpl": final_path,
            "cookiefile": get_cookie_file(),
            "geo_bypass": True,
            "nocheckcertificate": True,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True, # عشان ميكرشش لو فورمات واحد بايظ
            "extractor_args": extractor_args,
            "user_agent": get_user_agent(),
        }

        # تحديد الجودة (Fallback Strategy)
        if video:
            # حاول 720، لو مفيش هات أي فيديو وخلاص
            base_opts["format"] = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
        else:
            # حاول صوت بس، لو مفيش (بسبب الحظر) هات "أحسن جودة متاحة" وخد صوتها
            base_opts["format"] = "bestaudio/best"
        
        # إضافة Aria2 لو موجود للسرعة
        if self.has_aria2:
            base_opts["external_downloader"] = "aria2c"
            base_opts["external_downloader_args"] = ["-x", "16", "-s", "16", "-k", "1M"]

        # دالة التنفيذ
        def _run_download():
            if os.path.exists(final_path):
                return final_path
            
            with yt_dlp.YoutubeDL(base_opts) as ydl:
                try:
                    ydl.download([link])
                except Exception as e:
                    LOGGER(__name__).error(f"Download Failed: {e}")
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
    # 📺 باقي الوظائف
    # -----------------------------------------------------------------
    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid: link = self.listbase + link
        if "&" in link: link = link.split("&")[0]
        
        cmd = (
            f"yt-dlp -i --compat-options no-youtube-unavailable-videos "
            f"--get-id --flat-playlist --playlist-end {limit} --skip-download '{link}' "
            f"2>/dev/null"
        )
        # تنفيذ الأمر باستخدام subprocess
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
        
        # لجلب الصيغ المتاحة (يستخدم في التحميل اليدوي)
        ytdl_opts = {"quiet": True, "cookiefile": get_cookie_file()}
        with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
            formats_available = []
            try:
                r = ydl.extract_info(link, download=False)
                for format in r.get("formats", []):
                    # فلترة الصيغ البايظة
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
            a = VideosSearch(link, limit=10)
            result = (await a.next()).get("result")
            r = result[query_type]
            return r["title"], r["duration"], r["thumbnails"][0]["url"].split("?")[0], r["id"]
        except:
            return "Error", "0", "", "error"

# تصدير الكائن
YouTube = YouTubeAPI()
