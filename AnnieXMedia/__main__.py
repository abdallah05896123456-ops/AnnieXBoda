# =========================================================
# __main__.py (TitanOS Integrated - Realtime Sync Edition)
# =========================================================

import sys
import os
import asyncio
import importlib
import logging
from threading import Thread
from flask import Flask, render_template, request, redirect, url_for, Response, jsonify, session
from pyrogram import idle, Client

# ------------------------
# 1. إعدادات السيرفر
# ------------------------
BASE_DIR = os.getcwd()
TITAN_DIR = os.path.join(BASE_DIR, 'TitanOS')
if not os.path.exists(TITAN_DIR):
    TITAN_DIR = os.path.join(BASE_DIR, 'AnnieXMedia', 'TitanOS')

app = Flask(__name__, template_folder=TITAN_DIR, static_folder=TITAN_DIR)
app.secret_key = "Titan_God_Mode_2025"
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# بيانات الدخول
ADMIN_USER = "Abdallah"
ADMIN_PASS = "asdfghjkl05896"

# كاش التصميم
CSS_CACHE = ""
JS_CACHE = ""

def load_assets():
    global CSS_CACHE, JS_CACHE
    try:
        with open(os.path.join(TITAN_DIR, 'assets_bundle.txt'), "r", encoding="utf-8") as f:
            content = f.read()
            if "---CSS---" in content:
                parts = content.split("---JS---")
                CSS_CACHE = parts[0].split("---CSS---")[1].strip()
                JS_CACHE = parts[1].strip()
    except: pass
load_assets()

# ------------------------
# 2. Flask Routes
# ------------------------
@app.route('/static/css/style.css')
def serve_css():
    if not CSS_CACHE: load_assets()
    return Response(CSS_CACHE, mimetype='text/css')

@app.route('/static/js/app.js')
def serve_js():
    if not JS_CACHE: load_assets()
    return Response(JS_CACHE, mimetype='application/javascript')

@app.route('/')
def home():
    if session.get('user') == ADMIN_USER: return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_check():
    if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
        session['user'] = ADMIN_USER
        return redirect(url_for('dashboard'))
    return render_template('login.html', error="Access Denied")

@app.route('/dashboard')
def dashboard():
    if not session.get('user'): return redirect(url_for('home'))
    return render_template('dashboard.html')

# ------------------------
# 🔥 3. الـ API الذكي (The Brain) 🔥
# ------------------------

# أ) كشف الجروبات النشطة
@app.route('/api/active_calls', methods=['GET'])
def get_active_calls():
    if not session.get('user'): return jsonify({"ok": False}), 401
    
    active_data = []
    
    # دالة لجلب البيانات من داخل البوت (Async -> Sync)
    def fetch_data():
        from AnnieXMedia.core.call import StreamController
        # محاولة الوصول لقائمة المكالمات في pytgcalls
        try:
            # معظم السورسات بتخزن المكالمات هنا
            if hasattr(StreamController, 'call_py'):
                calls = StreamController.call_py.active_calls
            else:
                calls = [] # fallback
            return calls
        except:
            return []

    try:
        # تشغيل الكود في الـ Loop الأساسي للبوت
        future = asyncio.run_coroutine_threadsafe(
            _get_detailed_chats(), 
            bot_app.loop
        )
        active_data = future.result()
    except Exception as e:
        print(f"Error fetching calls: {e}")

    return jsonify({"ok": True, "chats": active_data})

# دالة مساعدة تجيب اسم الجروب كمان
async def _get_detailed_chats():
    from AnnieXMedia.core.call import StreamController
    results = []
    try:
        # بنحاول نجيب القائمة من Pytgcalls
        active_calls = StreamController.call_py.active_calls
        
        for chat_id in active_calls:
            try:
                # بنجيب اسم الجروب من التليجرام
                chat = await bot_app.get_chat(chat_id)
                chat_name = chat.title
            except:
                chat_name = f"Secret Group {chat_id}"
            
            results.append({
                "id": chat_id,
                "name": chat_name,
                "status": "Playing 🔊"
            })
    except:
        # لو فشل، بنرجع قائمة فاضية بدل ما السيستم يقع
        pass
    return results

# ب) تنفيذ الأوامر (Play/Pause/Skip)
@app.route('/api/<action>/<chat_id>', methods=['POST'])
def api_handler(action, chat_id):
    if not session.get('user'): return jsonify({"ok": False}), 401

    try:
        chat_id = int(chat_id)
        from AnnieXMedia.core.call import StreamController

        async def execute_order():
            if action == 'pause':
                await StreamController.pause_stream(chat_id)
            elif action == 'resume':
                await StreamController.resume_stream(chat_id)
            elif action in ['skip', 'stop']:
                await StreamController.stop_stream(chat_id)
            elif action == 'turbo':
                pass # مجرد تأثير بصري

        asyncio.run_coroutine_threadsafe(execute_order(), bot_app.loop).result()
        return jsonify({"ok": True, "msg": "Command Executed"})

    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

def run_flask():
    app.run(host="0.0.0.0", port=8080, use_reloader=False)

# ------------------------
# 4. تشغيل البوت
# ------------------------
sys.path.insert(0, os.getcwd())
import config
from AnnieXMedia import LOGGER, app as bot_app, userbot
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.misc import sudo
from AnnieXMedia.plugins import ALL_MODULES
from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies

async def init():
    # تشغيل السيرفر
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    LOGGER("TitanOS").info("✅ TitanOS Dashboard is Online on Port 8080")

    if not config.STRING1:
        LOGGER(__name__).error("No Session String!")
        exit()

    await sudo()
    try: await fetch_and_store_cookies()
    except: pass

    await bot_app.start()
    for mod in ALL_MODULES: importlib.import_module("AnnieXMedia.plugins" + mod)
    
    await userbot.start()
    await StreamController.start()
    await StreamController.decorators() # هام جداً لتفعيل الأوامر
    
    LOGGER("AnnieXMedia").info("🚀 System Fully Operational")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
