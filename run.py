import asyncio
import os
import sys

# تثبيت uvloop أول شيء قبل أي استيراد آخر
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    print("uvloop not found, falling back to default asyncio loop.")

# الآن نقوم باستيراد دالة التشغيل من السورس
from AnnieXMedia.__main__ import init

if __name__ == "__main__":
    try:
        # تشغيل البوت باستخدام Loop واحد موحد ومحسّن
        asyncio.run(init())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal Error: {e}")
