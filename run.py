# Authored By Certified Coders © 2025
# TitanOS Ultimate Engine: Force Loop Patch 🛡️

import asyncio
import logging
import sys

# 1. تفعيل uvloop فوراً
try:
    import uvloop
    uvloop.install()
except ImportError:
    pass

# إعدادات اللوج
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[logging.StreamHandler()]
)
LOGGER = logging.getLogger("TitanOS")

async def main():
    # استيراد ملفات البوت
    # بنستوردهم جوه الدالة عشان نضمن إنهم تحت سيطرتنا
    from AnnieXMedia import app, userbot
    from AnnieXMedia.core.call import StreamController
    from AnnieXMedia.__main__ import init
    
    LOGGER.info("⚡ Injecting correct Event Loop...")
    
    # الحصول على الـ Loop الحالي الشغال
    current_loop = asyncio.get_running_loop()
    
    # --- بداية الجراحة (Patching) ---
    # بنجبر البوت الأساسي والمساعد إنهم يستخدموا الـ Loop ده
    
    # 1. تعديل البوت الأساسي
    app.loop = current_loop
    userbot.loop = current_loop
    
    # 2. تعديل بوت الموسيقى (PyTgCalls) - ده سبب المشكلة عندك
    if hasattr(StreamController, 'one'):
        # تعديل العميل الداخلي للمساعد
        if hasattr(StreamController.one, '_app'):
            StreamController.one._app.loop = current_loop
        if hasattr(StreamController.one, '_bind_client'):
            StreamController.one._bind_client.loop = current_loop
            
    LOGGER.info("✅ Loop Injection Complete. Starting System...")
    
    # تشغيل البوت
    await init()

if __name__ == "__main__":
    try:
        # استخدام asyncio.run هو الطريقة الوحيدة الصحيحة
        asyncio.run(main())
    except KeyboardInterrupt:
        LOGGER.info("🛑 Stopped by user")
    except Exception as e:
        LOGGER.error(f"❌ Fatal Error: {e}", exc_info=True)
