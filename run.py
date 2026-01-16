# Authored By Certified Coders © 2025
# TitanOS Ultimate Engine: uvloop + Memory Optimization + Anti-Lag

import asyncio
import logging
import gc
import os
import sys

# محاولة استيراد uvloop
try:
    import uvloop
except ImportError:
    print("❌ Error: 'uvloop' is missing. Add it to requirements.txt")
    sys.exit(1)

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
    """
    دالة لضبط أداء بايثون لمنع التقطيع وتسريع المعالجة
    """
    # 1. ضبط Garbage Collector (منع التقطيع)
    # بنقلل عدد مرات تنظيف الذاكرة عشان المعالج يركز في الستريم والتحميل
    # القيم دي (700, 10, 10) متزنة جداً للبوتات الموسيقية
    try:
        gc.set_threshold(700, 10, 10)
        gc.enable()
        logger.info("✅ Garbage Collector Tuned for Streaming.")
    except Exception as e:
        logger.warning(f"⚠️ Could not tune GC: {e}")

def main():
    # 1. تفعيل تحسينات الأداء
    optimize_performance()

    # 2. تفعيل uvloop ليكون المدير الحصري للعمليات
    # uvloop.install() هي الطريقة الأحدث والأسرع من set_event_loop_policy
    uvloop.install()
    logger.info("🚀 uvloop Engine Activated (High Performance Mode).")

    # 3. إنشاء Loop جديد
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 4. تشغيل البوت
    try:
        logger.info("⚡ Starting AnnieXMedia Core...")
        
        # تشغيل الدالة الرئيسية
        loop.run_until_complete(init())
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot Process Stopped.")
    except Exception as e:
        logger.error(f"❌ Fatal Runtime Error: {e}", exc_info=True)
    finally:
        # تنظيف العمليات عند الإغلاق
        try:
            tasks = asyncio.all_tasks(loop)
            for task in tasks:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.close()
            logger.info("✅ Loop Closed Safely.")
        except:
            pass

if __name__ == "__main__":
    main()
