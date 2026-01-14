# Authored By Certified Coders © 2025
import sys
import os
import asyncio
import importlib
import threading
import logging

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

# ---------------------------------------------------
# ⚠️ التعديل هنا: الاستيراد من داخل AnnieXMedia
# ---------------------------------------------------
try:
    from AnnieXMedia.web import web_bp
except ImportError:
    # محاولة بديلة لو حصلت لخبطة في المسارات
    from web import web_bp

# ==========================================
# 🌐 إعداد الفلاسك (تعديل المسارات)
# ==========================================
# لاحظ هنا ضفنا AnnieXMedia قبل web
flask_app = Flask(__name__, 
                  template_folder='AnnieXMedia/web/templates', 
                  static_folder='AnnieXMedia/web/static')

flask_app.secret_key = "Titan_Glass_OS_Key"
flask_app.register_blueprint(web_bp)

def run_web_server():
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    _port = int(os.environ.get("PORT", 8080))
    print(f">> [TITAN OS] RUNNING INSIDE ANNIEX ON PORT {_port} 💎")
    
    flask_app.run(host="0.0.0.0", port=_port, debug=False, use_reloader=False)

# ==========================================
# 🤖 تشغيل البوت
# ==========================================

async def init():
    if (not config.STRING1 and not config.STRING2 and not config.STRING3 and not config.STRING4 and not config.STRING5):
        LOGGER(__name__).error("Session String Missing!")
        exit()

    try:
        await fetch_and_store_cookies()
        LOGGER("AnnieXMedia").info("Cookies Loaded ✅")
    except:
        pass

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

    LOGGER("AnnieXMedia.plugins").info("Modules Loaded...")

    await userbot.start()
    await StreamController.start()

    try:
        await StreamController.stream_call("AnnieXMedia/assets/test.mp4")
    except NoActiveGroupCall:
        LOGGER("AnnieXMedia").error("Please turn on Voice Chat in Logger Group!")
        exit()
    except:
        pass

    await StreamController.decorators()
    LOGGER("AnnieXMedia").info("💎 TITAN OS ONLINE 💎")
    
    await idle()
    await app.stop()
    await userbot.stop()

if __name__ == "__main__":
    # تشغيل الويب
    web_thread = threading.Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()

    # تشغيل البوت
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init())
