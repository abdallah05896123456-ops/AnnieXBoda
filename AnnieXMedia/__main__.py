# -*- coding: utf-8 -*-
# AnnieXMedia Main Runner | Titan OS Integration
# ────────────────────────────────────────────────────────

import asyncio
import importlib
import sys
import os
import threading
from sys import argv
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

# [1] استيراد موديولات البوت الأساسية
from AnnieXMedia import (
    LOGGER,
    app,
    userbot,
    YouTube,
)
from AnnieXMedia.misc import sudo
from AnnieXMedia.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS
import config

# ⚠️ التعديل الذكي لإصلاح خطأ (No module named modules/plugins)
# ─────────────────────────────────────────────────────────────
MODULE_TYPE = "modules" # الافتراضي
try:
    # المحاولة الأولى: مجلد modules
    from AnnieXMedia.modules import ALL_MODULES
    MODULE_TYPE = "modules"
except (ImportError, ModuleNotFoundError):
    try:
        # المحاولة الثانية: مجلد plugins (المستخدم في سورس AnnieXMusic)
        from AnnieXMedia.plugins import ALL_MODULES
        MODULE_TYPE = "plugins"
    except (ImportError, ModuleNotFoundError):
        print("❌ Critical Error: Could not find 'modules' or 'plugins' folder inside AnnieXMedia!")
        ALL_MODULES = []

# [2] إعداد وربط TitanOS Web Dashboard
# ────────────────────────────────────────────────────────
WEB_ENABLED = False

def setup_web_dashboard():
    """تهيئة واستيراد لوحة التحكم من مجلد TitanOS"""
    global WEB_ENABLED
    try:
        current_path = os.getcwd()
        if current_path not in sys.path:
            sys.path.append(current_path)

        from TitanOS.web_srv import start_server_thread
        return start_server_thread

    except ImportError:
        try:
            titan_path = os.path.join(current_path, "TitanOS")
            if os.path.exists(titan_path):
                sys.path.append(titan_path)
                from web_srv import start_server_thread
                return start_server_thread
        except Exception:
            pass
    return None

start_server_func = setup_web_dashboard()
if start_server_func:
    WEB_ENABLED = True


# [3] دالة التشغيل الرئيسية (Main Loop)
# ────────────────────────────────────────────────────────
async def init():
    # 1. التحقق من متغيرات المساعد
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        return

    # 2. تحميل قوائم الحظر
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    
    # 3. تفعيل السودو
    await sudo()

    # 4. تشغيل عملاء التيليجرام
    try:
        await app.start()
        for user in userbot.clients:
            await user.start()
    except Exception as ex:
        LOGGER(__name__).error(f"Bot failed to start: {ex}")
        exit()

    # 5. تحميل الإضافات (ديناميكياً حسب اسم المجلد)
    LOGGER("AnnieXMedia").info(f"Loading {MODULE_TYPE}...")
    for all_module in ALL_MODULES:
        # هنا التعديل المهم: استخدام المتغير بدلاً من الكلمة الثابتة
        importlib.import_module(f"AnnieXMedia.{MODULE_TYPE}." + all_module)
    LOGGER(f"AnnieXMedia.{MODULE_TYPE}").info("Successfully Imported Modules...")

    # 6. تشغيل لوحة التحكم (TitanOS Web Dashboard)
    # ────────────────────────────────────────────────────
    if WEB_ENABLED and start_server_func:
        try:
            LOGGER("TitanOS").info("🌐 Initializing Web Kernel...")
            server_thread = threading.Thread(target=start_server_func, daemon=True)
            server_thread.start()
            port = getattr(config, "PORT", 8080)
            LOGGER("TitanOS").info(f"✅ Dashboard is Live on Port: {port}")
        except Exception as web_e:
            LOGGER("TitanOS").error(f"❌ Failed to start Dashboard: {web_e}")

    # 7. إشعار البدء
    try:
        await app.send_message(
            config.LOG_GROUP_ID,
            f"<b>🔥 Titan OS Bot Started Successfully!</b>\n"
            f"<b>🖥 Web Dashboard:</b> {'Enabled ✅' if WEB_ENABLED else 'Disabled ❌'}\n"
            f"<b>📁 Modules Loaded:</b> {len(ALL_MODULES)} from <code>{MODULE_TYPE}</code>"
        )
    except:
        pass 

    LOGGER("AnnieXMedia").info("\x1b[32mBot Started Successfully. Hosting via TitanOS.\x1b[0m")
    
    await idle()

    # 8. إيقاف التشغيل
    try:
        await app.stop()
        for user in userbot.clients:
            await user.stop()
    except:
        pass
    LOGGER("AnnieXMedia").info("Stopping Bot Cleaning up...")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init())
