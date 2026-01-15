# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS | SYSTEM LAUNCHER
# ==============================================================================
# وظيفة هذا الملف هي تشغيل السيرفر (web_srv) بشكل آمن
# سواء تم تشغيل البوت يدوياً أو تم استدعاؤه كـ Plugin.
# ==============================================================================

import time
from . import web_srv

def init():
    """
    دالة التهيئة التي تستدعيها بعض سورسات البوتات (Yukki/Annie)
    """
    print("🔌 TitanOS: Initializing...")
    web_srv.start()

# إذا تم تشغيل الملف بشكل مباشر (للتجربة بدون بوت)
if __name__ == "__main__":
    print("🔧 TitanOS: Manual Start Mode")
    web_srv.start()
    
    # حلقة تكرار لإبقاء البرنامج يعمل (Keep-Alive)
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("🛑 TitanOS: Shutting Down...")

# إذا تم استدعاء الملف من داخل البوت (Import)
else:
    # نقوم بتشغيل السيرفر فوراً في الخلفية
    web_srv.start()
