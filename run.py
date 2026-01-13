# Authored By Certified Coders © 2025
# اسم الملف: run.py
# المكان: في المجلد الرئيسي (خارج AnnieXMedia)

import asyncio
import os
import sys

# 1. تفعيل uvloop كأول خطوة في حياة البوت (قبل استيراد أي شيء آخر)
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    print("✅ uvloop policy set successfully.")
except ImportError:
    print("⚠️ uvloop not installed, falling back to default asyncio loop.")

# 2. استدعاء دالة التشغيل من داخل السورس
# (نستدعيها بعد تفعيل الـ Policy لضمان أن البوت يعمل على Loop واحد)
from AnnieXMedia.__main__ import init

if __name__ == "__main__":
    print("🚀 Starting Bot via run.py...")
    try:
        # تشغيل البوت باستخدام asyncio.run
        asyncio.run(init())
    except KeyboardInterrupt:
        print("❌ Bot stopped by user.")
    except Exception as e:
        print(f"❌ Fatal Error: {e}")
