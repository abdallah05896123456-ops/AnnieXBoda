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
# تم إزالة LOADED_MODULES لأنها غير موجودة في السورس الخاص بك
from AnnieXMedia import (
    LOGGER,
    app,
    userbot,
    YouTube,
)
from AnnieXMedia.misc import sudo
from AnnieXMedia.modules import ALL_MODULES
from AnnieXMedia.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS
import config

# [2] إعداد وربط TitanOS Web Dashboard
# ────────────────────────────────────────────────────────
WEB_ENABLED = False

def setup_web_dashboard():
    """تهيئة واستيراد لوحة التحكم من مجلد TitanOS"""
    global WEB_ENABLED
    try:
        # إضافة المسار الحالي للتأكد من رؤية المجلدات الفرعية
        current_path = os.getcwd()
        if current_path not in sys.path:
            sys.path.append(current_path)

        # المحاولة الأولى: الاستيراد كحزمة (Package)
        # هذا يتطلب وجود ملف __init__.py داخل مجلد TitanOS
        from TitanOS.web_srv import start_server_thread
        return start_server_thread

    except ImportError:
        try:
            # المحاولة الثانية: إضافة مجلد TitanOS نفسه للمسارات
            # هذا يعمل حتى لو لم يكن هناك __init__.py
            titan_path = os.path.join(current_path, "TitanOS")
            if os.path.exists(titan_path):
                sys.path.append(titan_path)
                from web_srv import start_server_thread
                return start_server_thread
        except Exception as e:
            # لن نطبع خطأ كبير هنا حتى لا نملأ التيرمينال، فقط تحذير بسيط
            pass
    
    return None

# محاولة جلب دالة تشغيل السيرفر
start_server_func = setup_web_dashboard()
if start_server_func:
    WEB_ENABLED = True


# [3] دالة التشغيل الرئيسية (Main Loop)
# ────────────────────────────────────────────────────────
async def init():
    # 1. التحقق من متغيرات المساعد (Assistant Vars)
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        return

    # 2. تحميل قوائم الحظر (GBAN/Blocklist)
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    
    # 3. تفعيل صلاحيات المطورين (Sudo)
    await sudo()

    # 4. تشغيل عملاء التيليجرام (Clients Start)
    try:
        await app.start()
        for user in userbot.clients:
            await user.start()
    except Exception as ex:
        LOGGER(__name__).error(f"Bot failed to start: {ex}")
        exit()

    # 5. تحميل الإضافات والموديولات (Plugins)
    LOGGER("AnnieXMedia").info("Loading Modules...")
    for all_module in ALL_MODULES:
        importlib.import_module("AnnieXMedia.modules." + all_module)
    LOGGER("AnnieXMedia.modules").info("Successfully Imported Modules...")

    # 6. تشغيل لوحة التحكم (TitanOS Web Dashboard) 🚀
    # ────────────────────────────────────────────────────
    if WEB_ENABLED and start_server_func:
        try:
            LOGGER("TitanOS").info("🌐 Initializing Web Kernel...")
            
            # تشغيل السيرفر في Thread منفصل لعدم إيقاف البوت
            server_thread = threading.Thread(target=start_server_func, daemon=True)
            server_thread.start()
            
            port = getattr(config, "PORT", 8080)
            LOGGER("TitanOS").info(f"✅ Dashboard is Live on Port: {port}")
        except Exception as web_e:
            LOGGER("TitanOS").error(f"❌ Failed to start Dashboard: {web_e}")
    else:
        LOGGER("TitanOS").warning("⚠️ Dashboard Disabled: TitanOS folder or dependencies missing.")

    # 7. إشعار البدء لمجموعة السجل
    try:
        await app.send_message(
            config.LOG_GROUP_ID,
            f"<b>🔥 Titan OS Bot Started Successfully!</b>\n"
            f"<b>🖥 Web Dashboard:</b> {'Enabled ✅' if WEB_ENABLED else 'Disabled ❌'}\n"
            f"<b>🐍 Python:</b> {sys.version.split()[0]}\n"
            f"<b>⚡ Pyrogram:</b> v2.x"
        )
    except:
        pass 

    LOGGER("AnnieXMedia").info("\x1b[32mBot Started Successfully. Hosting via TitanOS.\x1b[0m")
    
    # 8. إبقاء البوت يعمل (Idle Loop)
    await idle()

    # 9. إيقاف التشغيل بأمان عند الخروج (CTRL+C)
    try:
        await app.stop()
        for user in userbot.clients:
            await user.stop()
    except:
        pass
    LOGGER("AnnieXMedia").info("Stopping Bot Cleaning up...")


if __name__ == "__main__":
    # تهيئة Loop وتشغيل الدالة الرئيسية
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init())
