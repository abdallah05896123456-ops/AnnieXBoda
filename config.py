# ── 𝚂ᴏᴜʀᴄᴇ ✘ 𝐁ᴏᴅᴀ © 2025 ──────────────────────────────────────────────────────
# Modified by: MusicBoda
# All Rights Reserved to the original creators & Boda Edits.

import re
import sys
from os import getenv
from dotenv import load_dotenv
from pyrogram import filters

# تحميل المتغيرات
load_dotenv()

# ===============================================================================
# 🌐 TITAN OS DASHBOARD CONFIGURATION (إعدادات الموقع)
# ===============================================================================
# كلمة سر الدخول للوحة التحكم
WEB_PASSWORD = getenv("WEB_PASSWORD", "asdfghjkl05896") 
# مفتاح التشفير (مهم للسيشنز في الموقع)
WEB_SECRET = getenv("WEB_SECRET", "AnnieX_Secret_Key_99123") 
# إعدادات السيرفر
HOST = getenv("HOST", "0.0.0.0")
PORT = int(getenv("PORT", "8080"))

# ===============================================================================
# 🤖 CORE BOT CONFIG (إعدادات البوت)
# ===============================================================================
try:
    API_ID = int(getenv("API_ID"))
    API_HASH = getenv("API_HASH")
except (TypeError, ValueError):
    print("🚫 خطأ: يجب وضع API_ID و API_HASH في متغيرات النظام (Vars/Secrets).")
    sys.exit()

BOT_TOKEN = getenv("BOT_TOKEN")

# معلومات المالك
OWNER_ID = int(getenv("OWNER_ID", 8313557781))
OWNER_USERNAME = getenv("OWNER_USERNAME", "CertifiedCoder")

# معلومات البوت
BOT_USERNAME = getenv("BOT_USERNAME", "SourceBodaBot")
BOT_NAME = getenv("BOT_NAME", "˹𝚂ᴏᴜʀᴄᴇ ✘ 𝐁ᴏᴅᴀ˼ ♪")
ASSUSERNAME = getenv("ASSUSERNAME", "SourceBodaAssistant")

# ===============================================================================
# 🗄️ DATABASE & LOGGING
# ===============================================================================
MONGO_DB_URI = getenv("MONGO_DB_URI")
LOGGER_ID = int(getenv("LOGGER_ID", -1003339220169))

# ===============================================================================
# ⚙️ LIMITS & SETTINGS
# ===============================================================================
DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 300))
SONG_DOWNLOAD_DURATION = int(getenv("SONG_DOWNLOAD_DURATION", "1200"))
SONG_DOWNLOAD_DURATION_LIMIT = int(getenv("SONG_DOWNLOAD_DURATION_LIMIT", "1800"))
TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", "157286400"))
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", "1288490189"))
PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", "30"))

# ===============================================================================
# 🎚️ STREAMING & DOWNLOAD QUALITY SETTINGS (جودات التشغيل والتنزيل)
# ===============================================================================

# الجودة الافتراضية لو المستخدم ما اختارش
DEFAULT_QUALITY = getenv("DEFAULT_QUALITY", "high")

# جودات الصوت والفيديو (تُستخدم في PyTgCalls + ffmpeg)
QUALITY_PRESETS = {
    # أقل جودة – أسرع تحميل (مناسب للسيرفرات الضعيفة)
    "low": {
        "audio_bitrate": "48k",
        "audio_samplerate": "22050",
        "video_bitrate": "300k",
        "description": "Low – Fast & Light"
    },

    # متوسطة – توازن
    "medium": {
        "audio_bitrate": "96k",
        "audio_samplerate": "44100",
        "video_bitrate": "600k",
        "description": "Medium – Balanced"
    },

    # عالية – الافتراضية (قريبة من Alexa)
    "high": {
        "audio_bitrate": "160k",
        "audio_samplerate": "48000",
        "video_bitrate": "1200k",
        "description": "High – Clear Audio"
    },

    # أعلى جودة ممكنة
    "best": {
        "audio_bitrate": "320k",
        "audio_samplerate": "48000",
        "video_bitrate": "2500k",
        "description": "Best – Studio Quality"
    },

    # صوت فقط (ممتاز للقرآن)
    "audio": {
        "audio_bitrate": "128k",
        "audio_samplerate": "44100",
        "video_bitrate": "800k",
        "description": "Audio Only – Quran & Nasheed"
    },
}
# ===============================================================================
# 🔗 EXTERNAL APIS
# ===============================================================================
COOKIE_URL = getenv("COOKIE_URL")
API_URL = getenv("API_URL")
VIDEO_API_URL = getenv("VIDEO_API_URL")
API_KEY = getenv("API_KEY")
DEEP_API = getenv("DEEP_API")

# ===============================================================================
# ☁️ DEPLOYMENT & GIT
# ===============================================================================
HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
HEROKU_API_KEY = getenv("HEROKU_API_KEY")

UPSTREAM_REPO = getenv("UPSTREAM_REPO", "https://t.me/SourceBoda")
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "Master")
GIT_TOKEN = getenv("GIT_TOKEN")

# روابط الدعم
SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/SourceBoda")
SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/music0587")

# مغادرة المساعد
AUTO_LEAVING_ASSISTANT = False
AUTO_LEAVE_ASSISTANT_TIME = int(getenv("ASSISTANT_LEAVE_TIME", "3600"))

DEBUG_IGNORE_LOG = True

# سبوتيفاي
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID", "22b6125bfe224587b722d6815002db2b")
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET", "c9c63c6fbf2f467c8bc68624851e9773")

# جلسات بايروجرام
STRING1 = getenv("STRING_SESSION")
STRING2 = getenv("STRING_SESSION2")
STRING3 = getenv("STRING_SESSION3")
STRING4 = getenv("STRING_SESSION4")
STRING5 = getenv("STRING_SESSION5")

# ===============================================================================
# 🎨 MEDIA & ASSETS
# ===============================================================================
START_VIDS = [
    "https://files.catbox.moe/b6533n.jpg",
    "https://files.catbox.moe/wqipfn.jpg",
    "https://files.catbox.moe/efzuds.jpg",
]

STICKERS = [
    "CAACAgQAAyEFAATHCHTJAAIToGlfMcgnOpNnuYnm1hlBTW_pZgZfAAIfFgAC-CS4UbtZNHZyyA3BHgQ",
    "CAACAgUAAyEFAATHCHTJAAITn2lfMb5VpY0QAom50knojYHju4bTAAILFQAC-vEZVMBmWHCQ-sJuHgQ",
]

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

# ===============================================================================
# 🛠️ HELPER FUNCTIONS & TEXTS
# ===============================================================================
def time_to_seconds(time: str) -> int:
    return sum(int(x) * 60**i for i, x in enumerate(reversed(time.split(":"))))

DURATION_LIMIT = time_to_seconds(f"{DURATION_LIMIT_MIN}:00")

AYU = [
    "جـاري الـتـشـغـيـل .. 🤍",
    "جـاري الـتـحـمـيـل .. 🫶",
    "لـحـظـة مـن فـضـلـك .. 🤍",
    "طـلـبـك قـيـد الـتـنـفـيـذ .. ☔",
    "يـتـم تـشـغـيـل الـتـراك .. 💝"
]

AYUV = [
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

# ===============================================================================
# 🚧 RUNTIME STRUCTURES
# ===============================================================================
BANNED_USERS = filters.user()
adminlist, lyrical, autoclean, confirmer = {}, {}, [], {}

if SUPPORT_CHANNEL and not re.match(r"^https?://", SUPPORT_CHANNEL):
    raise SystemExit("[ERROR] - Invalid SUPPORT_CHANNEL URL. Must start with https://")

if SUPPORT_CHAT and not re.match(r"^https?://", SUPPORT_CHAT):
    raise SystemExit("[ERROR] - Invalid SUPPORT_CHAT URL. Must start with https://")
