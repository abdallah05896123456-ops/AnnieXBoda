# -*- coding: utf-8 -*-
# =========================================================
# TITAN OS | FINAL KERNEL (AnnieXMedia Entry Point)
# =========================================================
# Path: AnnieXMedia/__main__.py
# =========================================================

import sys
import os
import asyncio
import importlib
import logging
import threading
from flask import Flask, request, redirect, url_for, jsonify, session, send_file, Response
from pyrogram import idle

# ---------------------------------------------------------
# [1] ضبط المسارات (Path Configuration)
# ---------------------------------------------------------
# 1. تحديد مكان ملف __main__.py الحالي (داخل مجلد AnnieXMedia)
PKG_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. تحديد المجلد الجذري (الذي يحتوي على AnnieXMedia و TitanOS)
ROOT_DIR = os.path.dirname(PKG_DIR)

# 3. تحديد مجلد TitanOS (حيث توجد ملفات html)
TITAN_DIR = os.path.join(ROOT_DIR, "TitanOS")
DOWNLOADS_DIR = os.path.join(ROOT_DIR, "downloads")

# إضافة الجذر للبايثون
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# التأكد من وجود مجلد TitanOS
if not os.path.exists(TITAN_DIR):
    print(f"⚠️ Warning: TitanOS folder not found at {TITAN_DIR}")

# إعداد Flask ليقرأ القوالب من مجلد TitanOS
app = Flask(__name__, template_folder=TITAN_DIR, static_folder=TITAN_DIR)
app.secret_key = "Titan_God_Mode_2025"

# إخفاء اللوجات المزعجة
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# بيانات الدخول
ADMIN_USER = "Abdallah"
ADMIN_PASS = "asdfghjkl05896"

# ---------------------------------------------------------
# [2] استيراد البوت (Bot Import)
# ---------------------------------------------------------
BOT_INITIALIZED = False
try:
    import config
    from AnnieXMedia import LOGGER, app as bot_app, userbot
    from AnnieXMedia.core.call import Annie as StreamController
    from AnnieXMedia.misc import sudo, db
    from AnnieXMedia.plugins import ALL_MODULES
    from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
    BOT_INITIALIZED = True
    print("✅ TitanOS: Connected to AnnieXMedia Core.")
except ImportError as e:
    print(f"⚠️ TitanOS Warning: Running in Web-Only Mode. Error: {e}")

# ---------------------------------------------------------
# [3] مسارات الموقع (Web Routes)
# ---------------------------------------------------------

@app.route('/')
def home():
    if session.get('user') == ADMIN_USER:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login_page'))

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
            session['user'] = ADMIN_USER
            return redirect(url_for('dashboard'))
        return "<h1>Wrong Password!</h1>"
    
    # قراءة الملف من مجلد TitanOS
    login_file = os.path.join(TITAN_DIR, "login.html")
    if os.path.exists(login_file):
        return send_file(login_file)
    return f"<h1>Login File Missing in {TITAN_DIR}</h1>"

@app.route('/dashboard')
def dashboard():
    if not session.get('user'): return redirect(url_for('login_page'))
    
    # قراءة الملف من مجلد TitanOS
    dash_file = os.path.join(TITAN_DIR, "dashboard.html")
    if os.path.exists(dash_file):
        return send_file(dash_file)
    return f"<h1>Error 404: dashboard.html not found in {TITAN_DIR}</h1>"

@app.route('/logs')
def view_logs():
    if not session.get('user'): return "Access Denied"
    log_file = os.path.join(ROOT_DIR, "log.txt") 
    if os.path.exists(log_file):
        return send_file(log_file, mimetype="text/plain")
    return "No logs found."

# ---------------------------------------------------------
# [4] بث الفيديو (Streaming Core)
# ---------------------------------------------------------
@app.route('/stream/<chat_id>')
def stream_video(chat_id):
    if not session.get('user'): return "Access Denied", 403
    
    file_path = None
    try:
        cid = int(chat_id)
        if BOT_INITIALIZED and cid in db and db[cid]:
            track = db[cid][0]
            file_path = track.get("file")
    except: pass

    # بحث احتياطي
    if not file_path and os.path.exists(DOWNLOADS_DIR):
        try:
            files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) if f.endswith(('mp4','mp3','webm'))]
            if files: file_path = max(files, key=os.path.getctime)
        except: pass

    if not file_path or not os.path.exists(file_path):
        return "No active stream found", 404

    # --- إصلاح مشكلة التقديم والتأخير (Range Support) ---
    range_header = request.headers.get('Range', None)
    if not range_header: return send_file(file_path)
    
    size = os.path.getsize(file_path)
    byte1, byte2 = 0, None
    m = range_header.replace('bytes=', '').split('-')
    byte1 = int(m[0])
    if m[1]: byte2 = int(m[1])
    length = size - byte1
    if byte2: length = byte2 + 1 - byte1
    
    with open(file_path, 'rb') as f:
        f.seek(byte1)
        data = f.read(length)
    
    rv = Response(data, 206, mimetype="video/mp4", direct_passthrough=True)
    rv.headers.add('Content-Range', f'bytes {byte1}-{byte1 + length - 1}/{size}')
    return rv

# ---------------------------------------------------------
# [5] API Control
# ---------------------------------------------------------
async def get_calls_safe():
    results = []
    try:
        calls = StreamController.active_calls if hasattr(StreamController, 'active_calls') else []
        for chat_id in calls:
            try:
                chat = await bot_app.get_chat(chat_id)
                results.append({"id": chat_id, "name": chat.title})
            except:
                results.append({"id": chat_id, "name": f"Chat {chat_id}"})
    except: pass
    return results

@app.route('/api/active_calls')
def api_active_calls():
    active_data = []
    if BOT_INITIALIZED:
        try:
            future = asyncio.run_coroutine_threadsafe(get_calls_safe(), bot_app.loop)
            active_data = future.result()
        except: pass
    # بيانات وهمية لو القائمة فارغة للتجربة
    if not active_data:
        active_data = [{"id": "0", "name": "Waiting for Calls..."}]
    return jsonify({"chats": active_data})

@app.route('/api/track_info/<chat_id>')
def api_track_info(chat_id):
    info = {"title": "Idle", "artist": "", "cover": "", "stream_url": ""}
    try:
        cid = int(chat_id)
        if BOT_INITIALIZED and cid in db and db[cid]:
            track = db[cid][0]
            info = {
                "title": track.get("title", "Unknown"),
                "artist": track.get("dur", "Live"),
                "cover": track.get("thumb", "https://telegra.ph/file/5eb6df308e92f4477813d.jpg"),
                "stream_url": f"/stream/{cid}"
            }
    except: pass
    return jsonify(info)

@app.route('/api/<cmd>/<chat_id>', methods=['POST'])
def api_command(cmd, chat_id):
    if not BOT_INITIALIZED: return jsonify({"ok": False})
    
    async def exec_cmd():
        try:
            cid = int(chat_id)
            if cmd == 'pause': await StreamController.pause_stream(cid)
            elif cmd == 'resume': await StreamController.resume_stream(cid)
            elif cmd == 'skip': await StreamController.stop_stream(cid)
        except: pass

    try:
        asyncio.run_coroutine_threadsafe(exec_cmd(), bot_app.loop)
    except: pass
    return jsonify({"ok": True})

@app.route('/api/system/turbo', methods=['POST'])
def turbo_mode():
    import gc
    gc.collect()
    return jsonify({"ok": True})

# ---------------------------------------------------------
# [6] التشغيل الرئيسي (Main Execution)
# ---------------------------------------------------------
def run_web():
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

async def main_init():
    print("---------------------------------------")
    print("🚀 TITAN OS IS LAUNCHING...")
    print("---------------------------------------")

    # 1. تشغيل الموقع في Thread منفصل
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()
    print("🌐 Dashboard: http://0.0.0.0:8080")

    # 2. تشغيل البوت
    if BOT_INITIALIZED:
        await sudo()
        try: await fetch_and_store_cookies()
        except: pass
        await bot_app.start()
        for mod in ALL_MODULES:
            importlib.import_module("AnnieXMedia.plugins" + mod)
        await userbot.start()
        await StreamController.start()
        try: await StreamController.decorators()
        except: pass
        print("🔥 Bot System Ready 🔥")
        await idle()
    else:
        # Loop للبقاء حياً لو البوت فشل
        while True: await asyncio.sleep(10)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main_init())
