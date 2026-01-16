# -*- coding: utf-8 -*-
# AnnieXMedia Main Runner | Titan OS Integration
# The Immortal Edition - Cookies & Anti-Crash Integrated
# ────────────────────────────────────────────────────────

import asyncio
import importlib
import sys
import os
import threading
from sys import argv
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

# إجبار البوت على استخدام المكتبات المحلية
sys.path.insert(0, os.getcwd())

# [1] استيراد موديولات البوت الأساسية
from AnnieXMedia import (
    LOGGER,
    app,
    userbot,
    YouTube,
)
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.misc import sudo
from AnnieXMedia.utils.database import get_banned_users, get_gbanned

# ✅ التعديل هنا: استدعاء ملف الكوكيز من utils وتسميته save_cookies
# عشان يشتغل مع باقي الكود تحت من غير تغيير
from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies as save_cookies

from config import BANNED_USERS
import config

# [2] استيراد قائمة الإضافات
try:
    from AnnieXMedia.plugins import ALL_MODULES
except ImportError:
    LOGGER("AnnieXMedia").error("Could not find 'plugins' folder or ALL_MODULES list!")
    exit()

# [3] تجهيز ربط موقعك الخاص (TitanOS)
CUSTOM_WEB_RUNNER = None
try:
    from AnnieXMedia.TitanOS.web_srv import start_server_thread
    CUSTOM_WEB_RUNNER = start_server_thread
    LOGGER("TitanOS").info("✅ Custom Dashboard File Found (web_srv.py).")
except ImportError as e:
    LOGGER("TitanOS").warning(f"⚠️ Custom Dashboard not found: {e}")

# [4] دالة التشغيل الرئيسية
async def init():
    # 1. التحقق من الجلسات
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant session variables not defined, exiting...")
        exit()

    # 2. ✅ تحميل الكوكيز (الآن يقرأ من المكان الصحيح)
    try:
        await save_cookies()
    except Exception as e:
        LOGGER("AnnieXMedia").warning(f"⚠️ Cookie Loader Error: {e}")

    # 3. إعدادات الحظر والسودو
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

    # 4. تشغيل البوت واليوزربوت
    await app.start()
    await userbot.start()

    # 5. تحميل الإضافات
    LOGGER("AnnieXMedia").info("Loading Plugins...")
    for all_module in ALL_MODULES:
        try:
            importlib.import_module("AnnieXMedia.plugins" + all_module)
        except Exception as e:
            LOGGER("AnnieXMedia").error(f"Failed to load plugin {all_module}: {e}")

    LOGGER("AnnieXMedia.plugins").info("Successfully Imported Plugins...")

    # 6. تشغيل نظام المكالمات
    await StreamController.start()
    try:
        # رابط تيست خفيف عشان ميعطلش التشغيل
        await StreamController.stream_call("http://docs.evostream.com/sample_content/assets/sintel1m720p.mp4")
    except NoActiveGroupCall:
        LOGGER("AnnieXMedia").error("Please turn on the Voice Chat of your Log Group.\nAnnie Bot Stopped...")
        exit()
    except Exception:
        pass

    await StreamController.decorators()

    # 7. تشغيل TitanOS Dashboard
    if CUSTOM_WEB_RUNNER:
        try:
            LOGGER("TitanOS").info("🌐 Initializing Your Custom Dashboard...")
            server_thread = threading.Thread(target=CUSTOM_WEB_RUNNER, daemon=True)
            server_thread.start()
            port = getattr(config, "PORT", 8080)
            LOGGER("TitanOS").info(f"✅ Dashboard should be live on port: {port}")
        except Exception as web_e:
            LOGGER("TitanOS").error(f"❌ Failed to start Custom Dashboard: {web_e}")
    else:
        LOGGER("TitanOS").warning("⚠️ No web server found. The bot is running without the dashboard.")

    # 8. رسالة البدء
    LOGGER("AnnieXMedia").info("\x1b[32mAnnie Music Bot & TitanOS Started Successfully.\x1b[0m")
    
    await idle()

    # 9. الإيقاف
    await app.stop()
    await userbot.stop()
    LOGGER("AnnieXMedia").info("Stopping Annie Music Bot...")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init())
