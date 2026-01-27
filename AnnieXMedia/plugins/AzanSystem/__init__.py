# __init__.py
# ملف تجميع وتشغيل نظام الأذان المتكامل
# ➻ sᴏᴜʀᴄᴇ : بُودَا | ʙᴏᴅَا

from AnnieXMedia import app

# 1. استيراد جميع الملفات لتسجيل الأوامر في البوت
from . import az_conf
from . import az_utils
from . import az_admin
from . import az_athkar
from . import az_quran
from . import az_broadcast

# 2. استيراد المجدول ودالة تهيئة النشر
from .az_utils import scheduler
from .az_broadcast import init_broadcast_schedule

# 3. تفعيل جدولة النشر التلقائي (الأذكار والصلاة على النبي)
# يتم دمجها مع المجدول الأساسي لتعمل فور تشغيله
try:
    init_broadcast_schedule(scheduler)
    print("[Azan System] تم تحميل نظام الأذان والنشر التلقائي بنجاح.")
except Exception as e:
    print(f"[Azan System] خطأ في تهيئة المجدول: {e}")
