# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS KERNEL — ULTIMATE STABILITY EDITION (4K CORE)
# Architecture: Multi-Threaded Flask + Async Pyrogram Bridge
# Status: Production Ready | Fail-Safe Enabled
# ==============================================================================

import os
import sys
import asyncio
import importlib
import logging
import threading
import time
import psutil
import traceback
import json
from flask import Flask, request, jsonify, session, send_file, redirect, url_for
from pyrogram import idle
from logging.handlers import RotatingFileHandler

# ------------------------------------------------------------------------------
# [1] SYSTEM CONFIGURATION & ROBUST PATH FINDING
# ------------------------------------------------------------------------------
# تحديد المسار بناءً على مكان الملف الحالي لضمان عدم حدوث أخطاء
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TITAN_DIR = os.path.join(BASE_DIR, "TitanOS")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
LOG_FILE = os.path.join(BASE_DIR, "titan.log")

# التأكد من وجود المجلدات الضرورية
os.makedirs(TITAN_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# ------------------------------------------------------------------------------
# [2] ADVANCED LOGGING SYSTEM (The Black Box)
# ------------------------------------------------------------------------------
# هذا النظام يسجل كل خطأ يحدث في ملف لتقرأه لاحقاً
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=2),
        logging.StreamHandler()
    ]
)
LOGGER = logging.getLogger("TitanKernel")
# إسكات رسائل Flask المزعجة للتركيز على الأخطاء الحقيقية
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# طباعة تقرير التشخيص عند البدء
print(f"\n{'='*50}")
print(f"🚀 TITAN OS: INITIALIZING SYSTEMS...")
print(f"📂 System Root: {BASE_DIR}")
print(f"📂 GUI Folder:  {TITAN_DIR}")
if not os.path.exists(os.path.join(TITAN_DIR, "login.html")):
    LOGGER.critical("⚠️ WARNING: 'login.html' is MISSING in TitanOS folder!")
else:
    print(f"✅ GUI Integrity Check Passed.")
print(f"{'='*50}\n")

# ------------------------------------------------------------------------------
# [3] GLOBAL STATE & CREDENTIALS
# ------------------------------------------------------------------------------
BOT_LOOP = None         # حلقة التكرار الخاصة بالبوت
START_TIME = time.time()
ADMIN_USER = os.environ.get("TITAN_USER", "Abdallah")
ADMIN_PASS = os.environ.get("TITAN_PASS", "asdfghjkl05896")

# ------------------------------------------------------------------------------
# [4] FLASK ENGINE (The Web Interface)
# ------------------------------------------------------------------------------
app = Flask(__name__, template_folder=TITAN_DIR, static_folder=TITAN_DIR)
app.secret_key = os.urandom(24)

# --- UTILS ---
def get_readable_time(seconds: int) -> str:
    count = 0
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]
    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0: break
        time_list.append(int(result))
        seconds = int(remainder)
    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4: time_list.pop()
    time_list.reverse()
    return ":".join(time_list) if time_list else "0s"

# --- ASYNC BRIDGE (The Magic Function) ---
# هذه الدالة هي السر: تسمح لـ Flask (Sync) بالتحدث مع البوت (Async) دون تعليق
def run_async_task(coro):
    if BOT_LOOP and BOT_LOOP.is_running():
        return asyncio.run_coroutine_threadsafe(coro, BOT_LOOP)
    return None

# --- WEB ROUTES ---

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect('/login')
    
    dash_file = os.path.join(TITAN_DIR, "dashboard.html")
    if os.path.exists(dash_file):
        return send_file(dash_file)
    return "<h1>Titan OS Active (Dashboard File Missing)</h1>"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # دعم استقبال البيانات كـ JSON أو Form
        try:
            u = request.form.get('username')
            p = request.form.get('password')
            
            if u == ADMIN_USER and p == ADMIN_PASS:
                session['logged_in'] = True
                LOGGER.info(f"✅ Successful Login by: {u}")
                return jsonify({"status": "success", "message": "Access Granted"})
            else:
                LOGGER.warning(f"❌ Failed Login Attempt: {u}")
                return jsonify({"status": "error", "message": "Invalid Credentials"}), 401
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    # GET Request
    if session.get('logged_in'): return redirect('/')
    login_file = os.path.join(TITAN_DIR, "login.html")
    if os.path.exists(login_file):
        return send_file(login_file)
    return "<h1>Titan OS: Login File Missing</h1>"

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# --- API ENDPOINTS (The Control Center) ---

@app.route('/api/settings/status')
def api_status():
    uptime = get_readable_time(int(time.time() - START_TIME))
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    
    # محاولة جلب البينج بأمان
    ping = 0
    try:
        if CallClient: ping = getattr(CallClient, "ping", 0)
    except: pass

    return jsonify({
        "status": "Online",
        "uptime": uptime,
        "cpu": cpu,
        "ram": ram,
        "ping": ping,
        "bot_connected": bool(bot_app and bot_app.is_connected)
    })

@app.route('/api/player/active_calls')
def api_active_calls():
    chats = []
    try:
        # جلب المكالمات الحية من البوت
        if CallClient and hasattr(CallClient, 'active_calls'):
            for cid in CallClient.active_calls:
                chat_info = {"chat_id": str(cid), "name": f"Chat {cid}", "cover": ""}
                # محاولة جلب التفاصيل من قاعدة البيانات
                if 'db' in globals() and cid in db:
                    try:
                        data = db[cid][0]
                        chat_info['name'] = data.get("title", chat_info['name'])
                        chat_info['cover'] = data.get("thumb", "")
                    except: pass
                chats.append(chat_info)
    except Exception as e:
        LOGGER.error(f"API Error (active_calls): {e}")
        
    return jsonify({"chats": chats})

@app.route('/api/player/control', methods=['POST'])
def api_control():
    if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    
    cmd = request.form.get('cmd')
    chat_id = request.form.get('chat_id')
    
    if not CallClient:
        return jsonify({"error": "Bot Core Not Ready"}), 503

    try:
        cid = int(chat_id)
        if cmd == 'pause':
            run_async_task(StreamController.pause_stream(cid))
        elif cmd == 'resume':
            run_async_task(StreamController.resume_stream(cid))
        elif cmd == 'skip':
            run_async_task(StreamController.stop_stream(cid))
        # إضافة المزيد من الأوامر هنا
        
        LOGGER.info(f"🕹️ Command Executed: {cmd} on {cid}")
        return jsonify({"status": "OK", "command": cmd})
    except Exception as e:
        LOGGER.error(f"Command Execution Failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/utils/logs')
def api_logs():
    """قراءة اللوجز مباشرة من المتصفح"""
    if not session.get('logged_in'): return "Auth Required", 401
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-100:] # آخر 100 سطر فقط
            return "<pre>" + "".join(lines) + "</pre>"
    except: return "No Logs Available"

# ------------------------------------------------------------------------------
# [5] BOT BOOTSTRAP (The Bridge Construction)
# ------------------------------------------------------------------------------
# تهيئة المتغيرات لتجنب الانهيار في حالة عدم وجود المكتبات
bot_app = None
userbot = None
CallClient = None
db = {}

def load_bot_modules():
    global bot_app, userbot, CallClient, db, StreamController
    try:
        LOGGER.info("🔌 Loading AnnieXMedia Core...")
        import config
        from AnnieXMedia import app as _bot, userbot as _ub
        from AnnieXMedia.core.call import StreamController as _SC
        from AnnieXMedia.misc import sudo as _sudo, db as _db
        from AnnieXMedia.plugins import ALL_MODULES
        from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
        
        # تعيين المتغيرات العامة
        bot_app = _bot
        userbot = _ub
        StreamController = _SC
        CallClient = _SC # Alias
        db = _db
        
        return True, ALL_MODULES, _sudo, fetch_and_store_cookies
    except ImportError as e:
        LOGGER.critical(f"❌ CRITICAL IMPORT ERROR: {e}")
        LOGGER.critical("👉 Ensure you are in the correct directory and requirements are installed.")
        return False, [], None, None

def run_flask_server():
    """تشغيل السيرفر في خيط منفصل لضمان عدم توقفه أبداً"""
    try:
        LOGGER.info("📡 Starting Web Interface on Port 8080...")
        # use_reloader=False مهم جداً عند استخدام Threads
        app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
    except Exception as e:
        LOGGER.critical(f"🔥 Web Server Crash: {e}")

async def start_bot_services():
    """تشغيل البوت والخدمات"""
    global BOT_LOOP
    BOT_LOOP = asyncio.get_running_loop()
    
    success, modules, sudo_func, cookie_func = load_bot_modules()
    
    if success:
        LOGGER.info("🍪 Fetching Cookies...")
        try: await cookie_func()
        except: pass
        
        LOGGER.info("🛡️ Initializing Sudo & DB...")
        await sudo_func()
        
        LOGGER.info("🤖 Starting Telegram Clients...")
        await bot_app.start()
        await userbot.start()
        
        LOGGER.info("🧩 Loading Plugins...")
        for mod in modules:
            try:
                importlib.import_module("AnnieXMedia.plugins" + mod)
            except Exception as e:
                LOGGER.error(f"Failed to load plugin {mod}: {e}")
        
        LOGGER.info("🎧 Starting Voice Client...")
        await StreamController.start()
        
        LOGGER.info("✅ TITAN OS KERNEL: ALL SYSTEMS ONLINE")
        await idle()
        
        LOGGER.info("🛑 Stopping Services...")
        await bot_app.stop()
        await userbot.stop()
    else:
        LOGGER.warning("⚠️ Running in WEB-ONLY Mode (Bot Failed to Load)")
        # إبقاء السكريبت يعمل حتى لو فشل البوت، لكي يعمل الموقع
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    # 1. تشغيل السيرفر (Web) في Thread منفصل
    # هذا يضمن أن الموقع يفتح فوراً حتى لو البوت يأخذ وقتاً للتشغيل
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()
    
    # 2. تشغيل البوت (Async) في الـ Main Thread
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_bot_services())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        LOGGER.critical(f"☠️ FATAL CRASH: {e}")
        traceback.print_exc()
