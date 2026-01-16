# Authored By Certified Coders © 2025
# Ultra High Performance Tuning (God Mode)

import asyncio
import os

CPU = os.cpu_count() or 4

# فتحنا الحد الأقصى للعمليات لأن uvloop بيقدر يشيل آلاف العمليات
MAX_CONCURRENT = 500

# 🔴 التغيير الجوهري هنا:
# خلينا حجم القراءة 4 ميجا بايت (بدل 128 كيلو)
# ده بيقلل الضغط على الهارد ديسك وبيخلي النت يشتغل بأقصى طاقة
CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB Buffer

# مهلة طويلة عشان لو النت علق لحظة ميفصلش التحميل
YTDLP_TIMEOUT = 300

# إعدادات الكاش لحفظ المعلومات أطول فترة ممكنة
YOUTUBE_META_TTL = 1800  # 30 دقيقة
YOUTUBE_META_MAX = 10000 # حفظ بيانات 10 آلاف فيديو

SEM = asyncio.Semaphore(MAX_CONCURRENT)
