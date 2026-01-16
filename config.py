# ── 𝚂ᴏᴜʀᴄᴇ ✘ 𝐁ᴏᴅᴀ © 2025 ──────────────────────────────────────────────────────
# Modified by: MusicBoda
# All Rights Reserved to the original creators & Boda Edits.

import re
import sys
from os import getenv
from dotenv import load_dotenv
from pyrogram import filters

# Load environment variables
load_dotenv()

# ── Core bot config (إعدادات البوت الأساسية) ───────────────────────────────────
try:
    API_ID = int(getenv("API_ID"))
    API_HASH = getenv("API_HASH")
except (TypeError, ValueError):
    print("🚫 خطأ: يجب وضع API_ID و API_HASH في متغيرات النظام (Vars/Secrets) ليعمل البوت.")
    sys.exit()

BOT_TOKEN = getenv("BOT_TOKEN")

# معلومات المالك
OWNER_ID = int(getenv("OWNER_ID", 8313557781))
OWNER_USERNAME = getenv("OWNER_USERNAME", "CertifiedCoder")

# معلومات البوت والمساعد
BOT_USERNAME = getenv("BOT_USERNAME", "SourceBodaBot")
BOT_NAME = getenv("BOT_NAME", "˹𝚂ᴏᴜʀᴄᴇ ✘ 𝐁ᴏᴅᴀ˼ ♪")
ASSUSERNAME = getenv("ASSUSERNAME", "SourceBodaAssistant")

# ── Database & logging ─────────────────────────────────────────────────────────
MONGO_DB_URI = getenv("MONGO_DB_URI")
LOGGER_ID = int(getenv("LOGGER_ID", -1003339220169))

# ── Limits ─────────────────────────────────────────────────────────────────────
DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 300))
SONG_DOWNLOAD_DURATION = int(getenv("SONG_DOWNLOAD_DURATION", "1200"))
SONG_DOWNLOAD_DURATION_LIMIT = int(getenv("SONG_DOWNLOAD_DURATION_LIMIT", "1800"))
TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", "157286400"))
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", "1288490189"))
PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", "30"))

# ── External APIs (تم التعديل هنا لربط السيرفر الجديد) ─────────────────────────
COOKIE_URL = getenv("COOKIE_URL")

# ✅ تم وضع رابط سيرفرك الجديد (Hyperion) مباشرة
API_URL = "https://hyperionengine.fly.dev"
VIDEO_API_URL = "https://hyperionengine.fly.dev"

# ✅ كلمة سر وهمية (السيرفر هيقبلها عادي)
API_KEY = "Titan123"

DEEP_API = getenv("DEEP_API")

# ── Hosting / deployment ───────────────────────────────────────────────────────
HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
HEROKU_API_KEY = getenv("HEROKU_API_KEY")

# ── Git / updates ──────────────────────────────────────────────────────────────
UPSTREAM_REPO = getenv("UPSTREAM_REPO", "https://t.me/SourceBoda")
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "Master")
GIT_TOKEN = getenv("GIT_TOKEN")

# ── Support links ──────────────────────────────────────────────────────────────
SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/SourceBoda")
SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/music0587")

# ── Assistant auto-leave ───────────────────────────────────────────────────────
AUTO_LEAVING_ASSISTANT = False
AUTO_LEAVE_ASSISTANT_TIME = int(getenv("ASSISTANT_LEAVE_TIME", "3600"))

# ── Debug ──────────────────────────────────────────────────────────────────────
DEBUG_IGNORE_LOG = True

# ── Spotify (optional) ─────────────────────────────────────────────────────────
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID", "22b6125bfe224587b722d6815002db2b")
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET", "c9c63c6fbf2f467c8bc68624851e9773")

# ── Session strings ────────────────────────────────────────────────────────────
STRING1 = getenv("STRING_SESSION")
STRING2 = getenv("STRING_SESSION2")
STRING3 = getenv("STRING_SESSION3")
STRING4 = getenv("STRING_SESSION4")
STRING5 = getenv("STRING_SESSION5")

# ── Media assets ───────────────────────────────────────────────────────────────
# فيديوهات الستارت
START_VIDS = [
    "https://files.catbox.moe/b6533n.jpg",
    "https://files.catbox.moe/wqipfn.jpg",
    "https://files.catbox.moe/efzuds.jpg",
]

# الاستيكرات
STICKERS = [
    "CAACAgQAAyEFAATHCHTJAAIToGlfMcgnOpNnuYnm1hlBTW_pZgZfAAIfFgAC-CS4UbtZNHZyyA3BHgQ",
    "CAACAgUAAyEFAATHCHTJAAITn2lfMb5VpY0QAom50knojYHju4bTAAILFQAC-vEZVMBmWHCQ-sJuHgQ",
]

# الصورة الموحدة
UNIFIED_IMG = "https://files.catbox.moe/tvmyz6.jpg"

START_IMG_URL = UNIFIED_IMG
HELP_IMG_URL = UNIFIED_IMG
PING_VID_URL = UNIFIED_IMG
PLAYLIST_IMG_URL = UNIFIED_IMG
STATS_VID_URL = UNIFIED_IMG
TELEGRAM_AUDIO_URL = UNIFIED_IMG
TELEGRAM_VIDEO_URL = UNIFIED_IMG
STREAM_IMG_URL = UNIFIED_IMG
SOUNCLOUD_IMG_URL = UNIFIED_IMG
YOUTUBE_IMG_URL = UNIFIED_IMG
SPOTIFY_ARTIST_IMG_URL = SPOTIFY_ALBUM_IMG_URL = SPOTIFY_PLAYLIST_IMG_URL = UNIFIED_IMG

# ── Helpers ────────────────────────────────────────────────────────────────────
def time_to_seconds(time: str) -> int:
    return sum(int(x) * 60**i for i, x in enumerate(reversed(time.split(":"))))

DURATION_LIMIT = time_to_seconds(f"{DURATION_LIMIT_MIN}:00")

# ───── نصوص التشغيل والتحميل المتنوعة ───── #
AYU = [
    "جـاري الـتـشـغـيـل .. 🤍",
    "جـاري الـتـحـمـيـل .. 🫶",
    "لـحـظـة مـن فـضـلـك .. 🤍",
    "طـلـبـك قـيـد الـتـنـفـيـذ .. ☔",
    "يـتـم تـشـغـيـل الـتـراك .. 💝"
]

# ───── رسالة الستارت العصرية ───── #
AYUV = [
    # ── رسالة الخاص (PM) ──
    """
صـلـي عـلـي الـنـبـي وتـبـسـم 🤍🌿.

مـرحـبـا انـا بـوت تـشـغـيـل صوتيات متطور ☔

أهـلاً بـك عـزيـزي {0} 🫶

وظـيـفـتـي تـشـغـيـل الـمـيـديـا فـي الـمـكـالـمـات بـجـودة عـالـيـة وبـدون تـقـطـيـع 🤍.

⧉ لـتـشـغـيـل أغـنـيـة اكـتـب « تشغيل + اسم الاغنية »
⧉ لـلـتـحـكـم فـي الـبـوت اضـغـط « الأوامـر » بـالأسـفـل 💝.

ـــــــــــــــــــــــــــــــــــــــــــــــــــــــ
⧉ وقـت الـعـمـل : {2}
⧉ الـرام : {5}
ـــــــــــــــــــــــــــــــــــــــــــــــــــــــ
    """,
    
    # ── رسالة المجموعات (Group) ──
    """
صـلـي عـلـي الـنـبـي وتـبـسـم 🤍🌿.

مـرحـبـا انـا بـوت تـشـغـيـل صوتيات متطور ☔

أهـلاً بـكـم فـي {0} 🫶
أنـا {1} .. جـاهـز لـخـدمـتـكـم 🤍.

⧉ أعـمـل بـكـفـاءة عـالـيـة بـدون تـوقـف.
⧉ فـقـط أضـفـنـي لـمـجـمـوعـتـك وارفـعـنـي مـشـرف 💝.

⧉ وقـت الـتـشـغـيـل : {2}
    """
]

# ── Runtime structures ─────────────────────────────────────────────────────────
BANNED_USERS = filters.user()
adminlist, lyrical, autoclean, confirmer = {}, {}, [], {}

# ── Minimal validation ─────────────────────────────────────────────────────────
if SUPPORT_CHANNEL and not re.match(r"^https?://", SUPPORT_CHANNEL):
    raise SystemExit("[ERROR] - Invalid SUPPORT_CHANNEL URL. Must start with https://")

if SUPPORT_CHAT and not re.match(r"^https?://", SUPPORT_CHAT):
    raise SystemExit("[ERROR] - Invalid SUPPORT_CHAT URL. Must start with https://")
