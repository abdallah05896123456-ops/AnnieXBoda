# Authored By Certified Coders © 2025
import sys
import os
import asyncio
import importlib
import threading
import logging # لإخفاء لوجات الفلاسك المزعجة

# السطر ده بيجبر البوت يستخدم مجلد pytgcalls المحلي بدل اللي نازل من النت
sys.path.insert(0, os.getcwd())

from flask import Flask
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from AnnieXMedia import LOGGER, app, userbot
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.misc import sudo
from AnnieXMedia.plugins import ALL_MODULES
from AnnieXMedia.utils.database import get_banned_users, get_gbanned
from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
from config import BANNED_USERS

# --- استدعاء الـ Route الخاص بالداشبورد ---
from AnnieXMedia.web.routes import web_bp

# ==========================================
# 🌐 إعــداد ســيــرفــر الــويــب (FLASK)
# ==========================================
flask_app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
flask_app.secret_key = "AnnieX_Titan_Key_2077"
flask_app.register_blueprint(web_bp)

def run_web_server():
    """تشغيل الموقع في خلفية السيرفر"""
    # إخفاء رسائل الفلاسك
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    print(">> [WEB] INITIALIZING DASHBOARD ON PORT 8080...")
    flask_app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

# ==========================================
# 🤖 إعــداد الــبــوت (ASYESNC)
# ==========================================

async def init():
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("لـم يـتـم إدخـال كـود جـلـسـة الـمـسـاعـد (Session)، يـرجـى الـتـحـقـق...")
        exit()

    # ✅ Try to fetch cookies at startup
    try:
        await fetch_and_store_cookies()
        LOGGER("AnnieXMedia").info("تـم تـحـمـيـل مـلـفـات كـوكـيـز يـوتـيـوب بـنـجـاح ✅")
    except Exception as e:
        LOGGER("AnnieXMedia").warning(f"⚠️ خـطـأ فـي الـكـوكـيـز: {e}")

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

    await app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("AnnieXMedia.plugins" + all_module)

    LOGGER("AnnieXMedia.plugins").info("تـم تـحـمـيـل مـلـفـات الـبـوت بـنـجـاح...")

    await userbot.start()
    await StreamController.start()

    try:
        # تشغيل ملف التست لضمان عمل الاتصال
        await StreamController.stream_call("AnnieXMedia/assets/test.mp4")
    except NoActiveGroupCall:
        LOGGER("AnnieXMedia").error(
            "يـرجـى فـتـح الـمـحـادثـة الـصـوتـيـة فـي مـجـمـوعـة الـسـجـل (Log Group) \n\n تـم إيـقـاف الـبـوت..."
        )
        exit()
    except:
        pass

    await StreamController.decorators()
    LOGGER("AnnieXMedia").info(
        "⚡️ ANNIE-X OS & DASHBOARD ONLINE ⚡️"
    )
    
    # الحفاظ على البوت يعمل حتى يتم إيقافه يدوياً
    await idle()
    
    await app.stop()
    await userbot.stop()
    LOGGER("AnnieXMedia").info("جـاري إيـقـاف الـبـوت...")


if __name__ == "__main__":
    # 1. تشغيل الويب سيرفر في خيط (Thread) منفصل عشان ميعطلش البوت
    web_thread = threading.Thread(target=run_web_server)
    web_thread.daemon = True # عشان يفصل لما البوت يفصل
    web_thread.start()

    # 2. تشغيل البوت الأساسي
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init())
