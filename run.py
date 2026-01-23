# Authored By Certified Coders © 2025
# TitanOS Ultimate Engine: Fixed Loop Mismatch & Import Order

import sys
import asyncio
import logging
import gc

# 1. تفعيل UVLoop قبل أي استيراد آخر (أهم خطوة لمنع الخطأ)
try:
    import uvloop
    uvloop.install()
    print("🚀 uvloop Installed Successfully (Fast Mode)")
except ImportError:
    print("⚠️ uvloop not found, falling back to asyncio")

# 2. الآن نستدعي البوت (بعد تفعيل المحرك)
# هذا الترتيب يضمن أن البوت يتعرف على المحرك الصحيح
from AnnieXMedia.__main__ import init

# إعدادات اللوج
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("log.txt")
    ]
)
logger = logging.getLogger("TitanOS")

def optimize_performance():
    """ضبط أداء الذاكرة"""
    try:
        gc.set_threshold(700, 10, 10)
        gc.enable()
        logger.info("✅ Garbage Collector Tuned.")
    except Exception as e:
        logger.warning(f"⚠️ GC Tuning Failed: {e}")

if __name__ == "__main__":
    optimize_performance()
    
    logger.info("⚡ Starting AnnieXMedia Core...")
    
    try:
        # استخدام asyncio.run هو الطريقة الصحيحة مع Python 3.12
        # هذا ينشئ الـ Loop ويديره ويغلقه تلقائياً بدون تعارض
        asyncio.run(init())
    except KeyboardInterrupt:
        logger.info("🛑 Bot Process Stopped by User.")
    except Exception as e:
        logger.error(f"❌ Fatal Error: {e}", exc_info=True)
