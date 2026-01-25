# Authored By Certified Coders © 2025
# Optimized by TitanOS for RAM Disk Usage

import os
import shutil
from ..logging import LOGGER

BASE_DIR = os.path.abspath(os.getcwd())

# 🔥 التعديل الجوهري هنا 🔥
# بنفحص لو الرام ديسك متاح في النظام (موجود في لينكس ودوكر)
if os.path.exists("/dev/shm"):
    # استخدام الرام كمكان للتحميل (سرعة خرافية + بدون تقطيع)
    DOWNLOAD_DIR = os.path.join("/dev/shm", "AnnieDownloads")
else:
    # Fallback: العودة للهارد العادي لو الرام مش متاحة
    DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

CACHE_DIR = os.path.join(BASE_DIR, "cache")
COUPLE_DIR = os.path.join(BASE_DIR, "couples")
BACKUP_DIR = os.path.join(BASE_DIR, "AnnieXMediaBackup")


def StorageManager():
    # تنظيف الرام عند التشغيل لمنع امتلاء الذاكرة
    if os.path.exists("/dev/shm") and "AnnieDownloads" in DOWNLOAD_DIR:
        try:
            if os.path.exists(DOWNLOAD_DIR):
                shutil.rmtree(DOWNLOAD_DIR)
                LOGGER(__name__).info("🧹 RAM Disk Cleaned Successfully.")
        except Exception as e:
            LOGGER(__name__).warning(f"Failed to clean RAM Disk: {e}")

    for path in (
        DOWNLOAD_DIR,
        CACHE_DIR,
        COUPLE_DIR,
        BACKUP_DIR,
    ):
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as e:
            LOGGER(__name__).error(f"Failed creating dir {path}: {e}")

    LOGGER(__name__).info(f"Directories Updated. Downloads pointed to: {DOWNLOAD_DIR}")
