# -*- coding: utf-8 -*-
# =========================================================
# TITAN OS | FINAL KERNEL (Fixed Paths)
# =========================================================

import sys
import os
import asyncio
import importlib
import logging
import threading
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, send_file, Response
from pyrogram import idle

# ---------------------------------------------------------
# [1] إصلاح المسارات (الحل الجذري للمشكلة)
# ---------------------------------------------------------
# 1. تحديد مكان ملف main.py الحالي (داخل TitanOS)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. تحديد المجلد الرئيسي للبوت (المجلد الذي يحتوي على AnnieXMedia)
ROOT_DIR = os.path.dirname(CURRENT_DIR)

# 3. إضافة المجلد الرئيسي للبايثون عشان يقدر يعمل import للبوت
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# إعداد فلاسك ليقرأ من المجلد الصحيح (TitanOS)
app = Flask(__name__, template_folder=CURRENT_DIR, static_folder=CURRENT_DIR)
app.secret_key = "Titan_God_Mode_2025"

# إخفاء اللوجات
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# بيانات الدخول
ADMIN_USER = "Abdallah"
ADMIN_PASS = "asdfghjkl05896"

# ---------------------------------------------------------
# [2] استيراد البوت بأمان
# ---------------------------------------------------------
BOT_INITIALIZED = False
try:
    import config
    from AnnieXMedia import LOGGER, app as bot_app, userbot
    from AnnieXMedia.core.call import StreamController
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
        return render_template_string_custom("<h1>Wrong Password!</h1>")
    
    # استخدام send_file لضمان قراءة الملف الصحيح
    login_file = os.path.join(CURRENT_DIR, "login.html")
    if os.path.exists(login_file):
        return send_file(login_file)
    
    # واجهة طوارئ لو الملف مش موجود
    return "<h1>Login File Missing</h1>"

@app.route('/dashboard')
def dashboard():
    if not session.get('user'): return redirect(url_for('login_page'))
    
    # هنا الإصلاح: استخدام CURRENT_DIR
    dash_file = os.path.join(CURRENT_DIR, "dashboard.html")
    if os.path.exists(dash_file):
        return send_file(dash_file)
    return f"<h1>Error 404: dashboard.html not found in {CURRENT_DIR}</h1>"

@app.route('/logs')
def view_logs():
    if not session.get('user'): return "Access Denied"
    # قراءة ملف اللوج من المجلد الرئيسي
    log_file = os.path.join(ROOT_DIR, "log.txt") 
    if os.path.exists(log_file):
        return send_file(log_file, mimetype="text/plain")
    return "No logs found."

# ---------------------------------------------------------
# [4] بث الفيديو (Streaming)
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

    # بحث احتياطي في مجلد التحميلات
    if not file_path:
        dl_dir = os.path.join(ROOT_DIR, "downloads")
        if os.path.exists(dl_dir):
            files = [os.path.join(dl_dir, f) for f in os.listdir(dl_dir) if f.endswith(('mp4','mp3','webm'))]
            if files: file_path = max(files, key=os.path.getctime)

    if file_path and os.path.exists(file_path):
        return send_file(file_path)
    
    return "No active stream found", 404

# ---------------------------------------------------------
# [5] API Control
# ---------------------------------------------------------
@app.route('/api/active_calls')
def api_active_calls():
    active_data = []
    if BOT_INITIALIZED:
        try:
            # طريقة آمنة لجلب البيانات من الـ Loop الآخر
            future = asyncio.run_coroutine_threadsafe(get_calls_safe(), bot_app.loop)
            active_data = future.result()
        except: pass
    return jsonify({"chats": active_data})

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
# [6] التشغيل (The Launcher)
# ---------------------------------------------------------
def run_web():
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

async def main_init():
    # 1. تشغيل الموقع في الخلفية
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()
    
    print("🚀 TitanOS Dashboard: http://0.0.0.0:8080")

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
        print("🔥 System Ready 🔥")
        await idle()
    else:
        # لو البوت فشل، خلي الموقع شغال بس
        while True: await asyncio.sleep(10)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main_init())
