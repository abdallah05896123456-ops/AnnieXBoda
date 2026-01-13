# Authored By Certified Coders © 2025
import sys
import os
import asyncio
import importlib

# هـذا السطـر يـجـبـر الـبـوت عـلـى استخـدام مـكـتـبـة pytgcalls المـحـلـيـة
sys.path.insert(0, os.getcwd())

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

# الدالة الرئيسية (تم تنظيفها لتستدعى من run.py)
async def init():
    # 👇👇👇 بدايـة الإصـلاح (Loop Fix) 👇👇👇
    # هـذا الـجـزء هـو الـذي سـيـحـل مـشـكـلـة "attached to a different loop"
    try:
        current_loop = asyncio.get_running_loop()
        
        # نـقـل الـبـوت لـلـعـمـل عـلـى الـ Loop الـجـديـد
        if hasattr(app, "loop"):
            app.loop = current_loop
        if hasattr(app, "session"):
            app.session = None  # إعـادة تـهـيـئـة الـجـلـسـة

        # نـقـل الـيـوزر بـوت لـلـعـمـل عـلـى الـ Loop الـجـديـد
        if hasattr(userbot, "loop"):
            userbot.loop = current_loop
        if hasattr(userbot, "session"):
            userbot.session = None

        LOGGER("AnnieXMedia").info("✅ تـم ضـبـط الـ Loop بـنـجـاح لـمـنـع الـتـعـارض.")
    except Exception as e:
        LOGGER("AnnieXMedia").warning(f"⚠️ تـحـذيـر Loop: {e}")
    # 👆👆👆 نـهـايـة الإصـلاح 👆👆👆


    # الـتـحـقـق مـن وجـود كـود جـلـسـة (Session) واحـد عـلـى الأقـل
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("لـم يـتـم إدخـال كـود جـلـسـة الـمـسـاعـد (Session)، يـرجـى الـتـحـقـق...")
        exit()

    # ✅ مـحـاولـة جـلـب مـلـفـات الـكـوكـيـز لـلـيـوتـيـوب
    try:
        await fetch_and_store_cookies()
        LOGGER("AnnieXMedia").info("تـم تـحـمـيـل مـلـفـات كـوكـيـز يـوتـيـوب بـنـجـاح ✅")
    except Exception as e:
        LOGGER("AnnieXMedia").warning(f"⚠️ خـطـأ فـي الـكـوكـيـز: {e}")


    await sudo()

    # تـحـمـيـل قـوائـم الـحـظـر
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass

    # بـدء تـشـغـيـل الـبـوت الأسـاسـي
    try:
        await app.start()
    except Exception as e:
        LOGGER("AnnieXMedia").error(f"فشل تشغيل البوت: {e}")
        exit()
    
    # تـحـمـيـل الـمـلـفـات (Plugins)
    for all_module in ALL_MODULES:
        importlib.import_module("AnnieXMedia.plugins" + all_module)

    LOGGER("AnnieXMedia.plugins").info("تـم تـحـمـيـل مـلـفـات الـبـوت بـنـجـاح...")

    # بـدء تـشـغـيـل الـحـسـاب الـمـسـاعـد ومـتـحـكـم الـمـكـالـمـات
    try:
        await userbot.start()
    except Exception as e:
        LOGGER("AnnieXMedia").error(f"فشل تشغيل اليوزربوت: {e}")
        exit()

    await StreamController.start()

    # مـحـاولـة دخـول الـكـول وتـشـغـيـل فـيـديـو الاخـتـبـار
    try:
        # ✅ تـم ضـبـط الـمـسـار لـيـعـمـل عـلـى مـلـفـك الـجـديـد
        await StreamController.stream_call("AnnieXMedia/assets/test.mp4")
    except NoActiveGroupCall:
        LOGGER("AnnieXMedia").error(
            "يـرجـى فـتـح الـمـحـادثـة الـصـوتـيـة فـي مـجـمـوعـة الـسـجـل (Log Group) \n\n تـم إيـقـاف الـبـوت..."
        )
        exit()
    except:
        pass

    await StreamController.decorators()
    
    # رسـالـة الـنـجـاح الـنـهـائـيـة
    LOGGER("AnnieXMedia").info(
        "تـم تـشـغـيـل بـوت الـمـيـوزك بـنـجـاح... جـاهـز لـلاسـتـخـدام ⚡️"
    )
    
    await idle()
    
    # عـنـد الإيـقـاف
    await app.stop()
    await userbot.stop()
    LOGGER("AnnieXMedia").info("جـاري إيـقـاف الـبـوت...")
