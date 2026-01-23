# Authored By Certified Coders © 2025
# TitanOS Ultimate Engine: Loop Mismatch Fix 🛡️

import asyncio
import logging
import sys
import os

# 1. تفعيل uvloop وإنشاء المحرك (أول خطوة إجبارية)
try:
    import uvloop
    uvloop.install()
except ImportError:
    print("⚠️ uvloop not installed, using default asyncio")

# 2. إنشاء الـ Loop يدوياً وتعيينه كـ Global
# الخطوة دي بتجبر أي كود يجي بعدها إنه يستخدم الـ Loop ده
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# 3. استيراد البوت (لاحظ: الاستيراد لازم يكون هنا بعد إنشاء الـ Loop)
# لو حطيت السطر ده فوق، المشكلة هتتكرر
from AnnieXMedia.__main__ import init
from AnnieXMedia import LOGGER

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

if __name__ == "__main__":
    LOGGER("TitanOS").info("✅ System Loop configured successfully.")
    LOGGER("TitanOS").info("⚡ Starting AnnieXMedia Core...")

    try:
        # تشغيل البوت باستخدام الـ Loop اللي عملناه فوق
        loop.run_until_complete(init())
    except KeyboardInterrupt:
        LOGGER("TitanOS").info("🛑 Bot Process Stopped by User.")
    except Exception as e:
        LOGGER("TitanOS").error(f"❌ Fatal Error: {e}", exc_info=True)
    finally:
        # تنظيف الذاكرة عند الإغلاق
        try:
            tasks = asyncio.all_tasks(loop)
            for task in tasks:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.close()
        except:
            pass
