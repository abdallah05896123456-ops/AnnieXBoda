import asyncio
import os

# 🔥 Fly.io Aggressive Mode
# نستخدم كل الكورات المتاحة + 4 Threads إضافية لضمان عدم توقف الـ I/O
CPU = (os.cpu_count() or 2) + 4

# ⚠️ التوازن الذهبي (Speed vs Capacity):
# 6 مستخدمين بسرعة صاروخ أفضل من 12 مستخدم بسرعة سلحفاة.
MAX_CONCURRENT = 8

# 🚀 THE SPACE CHUNK (10MB):
# الرقم السحري لخداع يوتيوب وضخ البيانات بأقصى سرعة.
CHUNK_SIZE = 10485760 

# ⏳ Timeouts
YTDLP_TIMEOUT = 300 

# 🧠 Meta Cache (الذاكرة)
YOUTUBE_META_TTL = 1200  
YOUTUBE_META_MAX = 10000 

# السيمفور (شرطي المرور)
SEM = asyncio.Semaphore(MAX_CONCURRENT)

# ====================================================
# 🚀 ARIA2C TURBO CONFIGURATION (محرك السرعة)
# ====================================================

# هذه الإعدادات تجبر Aria2c على فتح 16 خط اتصال في نفس اللحظة
# مما يضاعف سرعة التحميل حرفياً (Multi-Connection Download)
ARIA_OPTIONS = {
    'external_downloader': 'aria2c',
    'external_downloader_args': [
        '-x', '16',   # فتح 16 خط اتصال (الحد الأقصى المسموح به ليوتيوب)
        '-s', '16',   # تقسيم الملف إلى 16 قطعة
        '-j', '16',   # تحميل 16 قطعة بالتوازي
        '-k', '1M',   # حجم القطعة الواحدة (صغير لتسريع البدء)
        '--file-allocation=none', # توفير وقت حجز المساحة على القرص
    ]
}

# دمج الخيارات الأساسية مع خيارات السرعة
YTDLP_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': '%(id)s.%(ext)s',
    'geo_bypass': True,
    'nocheckcertificate': True,
    'quiet': True,
    'no_warnings': True,
    'hls_prefer_native': True,     # سرعة أفضل في البث المباشر
    'cookiefile': 'cookies.txt',   # ضروري لتفادي الحظر
    **ARIA_OPTIONS,                # ✅ تفعيل Aria2c هنا
}
