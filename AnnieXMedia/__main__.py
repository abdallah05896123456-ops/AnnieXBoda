# ================================
# __main__.py AnnieXMedia (Corrected)
# ================================

import sys
import os
import asyncio
import importlib
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

# ------------------------
# Paths: إعداد مسارات البوت
# ------------------------
# إجبار البوت يستخدم المسار الحالي كـ Root Package
sys.path.insert(0, os.getcwd())

# ------------------------
# استيراد مكتبات AnnieXMedia الأساسية
# ------------------------
import config
from AnnieXMedia import LOGGER, app, userbot
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.misc import sudo
from AnnieXMedia.plugins import ALL_MODULES
from AnnieXMedia.utils.database import get_banned_users, get_gbanned
from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
from config import BANNED_USERS

# ------------------------
# 🔥 استيراد ملفات WEB (التصحيح هنا) 🔥
# ------------------------
try:
    from AnnieXMedia.web import Resource_Optimizer
    from AnnieXMedia.web import backend_bridge
    from AnnieXMedia.web import security_gate
    LOGGER("AnnieXMedia.web").info("✅ Web Modules Loaded Successfully")
except ImportError as e:
    LOGGER("AnnieXMedia.web").error(f"❌ Failed to load Web Modules: {e}")
    # لن نوقف البوت، سيكمل العمل بدون الويب مؤقتاً
except Exception as e:
    LOGGER("AnnieXMedia.web").error(f"❌ Critical Error in Web Files: {e}")

# ========================
# دالة Init لتشغيل كل شيء
# ========================
async def init():
    # 1. التحقق من وجود Session
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error(
            "ᴀssɪsᴛᴀɴᴛ sᴇssɪᴏɴ ɴᴏᴛ ғɪʟʟᴇᴅ, ᴘʟᴇᴀsᴇ ғɪʟʟ ᴀ ᴘʏʀᴏɢʀᴀᴍ sᴇssɪᴏɴ..."
        )
        exit()

    # 2. تحميل الكوكيز
    try:
        await fetch_and_store_cookies()
        LOGGER("AnnieXMedia").info("ʏᴏᴜᴛᴜʙᴇ ᴄᴏᴏᴋɪᴇs ʟᴏᴀᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ ✅")
    except Exception as e:
        LOGGER("AnnieXMedia").warning(f"⚠️ᴄᴏᴏᴋɪᴇ ᴇʀʀᴏʀ: {e}")

    # 3. تهيئة الصلاحيات وقوائم الحظر
    await sudo()
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass

    # 4. تشغيل البوت (Client)
    await app.start()
    LOGGER("AnnieXMedia").info("✅ Bot Client Started")

    # 5. تحميل الـ Plugins
    for all_module in ALL_MODULES:
        importlib.import_module("AnnieXMedia.plugins" + all_module)
    LOGGER("AnnieXMedia.plugins").info("✅ Annie's Modules Loaded...")

    # 6. تشغيل المساعد والمشغل
    await userbot.start()
    await StreamController.start()

    # 7. اختبار Voice Chat
    try:
        await StreamController.stream_call(
            "http://docs.evostream.com/sample_content/assets/sintel1m720p.mp4"
        )
    except NoActiveGroupCall:
        LOGGER("AnnieXMedia").error(
            "⚠️ Please turn on the Video Chat in your Log Group!\n"
            "Bot is stopping..."
        )
        exit()
    except Exception:
        pass

    # 8. تشغيل Decorators و Idle
    await StreamController.decorators()
    LOGGER("AnnieXMedia").info("🚀 Annie Music Robot Started Successfully...")
    
    await idle()

    # 9. إغلاق نظيف
    await app.stop()
    await userbot.stop()
    LOGGER("AnnieXMedia").info("Stopping Annie Music Bot...")

# ========================
# نقطة الدخول
# ========================
if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
