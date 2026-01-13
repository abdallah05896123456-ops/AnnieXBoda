# Authored By Certified Coders © 2025
import sys
import os
import asyncio
import importlib

sys.path.insert(0, os.getcwd())

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from AnnieXMedia import LOGGER, app, userbot
from AnnieXMedia.misc import sudo
from AnnieXMedia.plugins import ALL_MODULES
from AnnieXMedia.utils.database import get_banned_users, get_gbanned
from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
from config import BANNED_USERS

# ⚠️ إزالة StreamController من هنا (سنستدعيه بالداخل)

async def init():
    # 👇👇👇 إصلاح شامل للـ Loop (Bot + Userbot + Assistants) 👇👇👇
    try:
        current_loop = asyncio.get_running_loop()
        
        # 1. إصلاح البوت
        if hasattr(app, "loop"): app.loop = current_loop
        if hasattr(app, "session"): app.session = None

        # 2. إصلاح اليوزربوت الرئيسي
        if hasattr(userbot, "loop"): userbot.loop = current_loop
        if hasattr(userbot, "session"): userbot.session = None

        # 3. إصلاح المساعدين الداخليين (مهم جداً)
        # أغلب السورسات تخزن المساعدين في قائمة assistants أو متغيرات one, two...
        if hasattr(userbot, "assistants"):
            for assistant in userbot.assistants:
                if hasattr(assistant, "loop"): assistant.loop = current_loop
                if hasattr(assistant, "session"): assistant.session = None
        
        # محاولة إصلاح إضافية للمتغيرات الفردية (احتياط)
        for attr in ["one", "two", "three", "four", "five"]:
            if hasattr(userbot, attr):
                cli = getattr(userbot, attr)
                if cli:
                    if hasattr(cli, "loop"): cli.loop = current_loop
                    if hasattr(cli, "session"): cli.session = None

        LOGGER("AnnieXMedia").info("✅ تـم تـحـديـث الـ Loop لـجـمـيـع الـحـسـابـات.")
    except Exception as e:
        LOGGER("AnnieXMedia").warning(f"⚠️ تحذير Loop Fix: {e}")
    # 👆👆👆 نهاية الإصلاح 👆👆👆

    # ✅ استدعاء StreamController هنا (لضمان أنه يأخذ الـ Loop الجديد)
    # هذا سيحل مشكلة PyTgCalls attached to different loop
    from AnnieXMedia.core.call import StreamController

    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("لـم يـتـم إدخـال كـود جـلـسـة الـمـسـاعـد...")
        exit()

    try:
        await fetch_and_store_cookies()
        LOGGER("AnnieXMedia").info("تـم تـحـمـيـل كوكيز يوتـيوب ✅")
    except Exception as e:
        LOGGER("AnnieXMedia").warning(f"⚠️ خـطـأ كوكيز: {e}")

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

    try:
        await app.start()
    except Exception as e:
        LOGGER("AnnieXMedia").error(f"فشل تشغيل البوت: {e}")
        exit()
    
    for all_module in ALL_MODULES:
        importlib.import_module("AnnieXMedia.plugins" + all_module)

    LOGGER("AnnieXMedia.plugins").info("تـم تـحـمـيـل الـمـلـفـات...")

    try:
        await userbot.start()
    except Exception as e:
        LOGGER("AnnieXMedia").error(f"فشل تشغيل اليوزربوت: {e}")
        exit()

    # الآن StreamController سيعمل لأننا استدعيناه في الداخل
    await StreamController.start()

    try:
        await StreamController.stream_call("AnnieXMedia/assets/test.mp4")
    except NoActiveGroupCall:
        LOGGER("AnnieXMedia").error("يرجى فتح المكالمة في مجموعة السجل!")
        exit()
    except:
        pass

    await StreamController.decorators()
    LOGGER("AnnieXMedia").info("تـم الـتـشـغـيـل بـنـجـاح ⚡️")
    
    await idle()
    
    await app.stop()
    await userbot.stop()
