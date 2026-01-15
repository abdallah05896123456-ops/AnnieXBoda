# -*- coding: utf-8 -*-
# =========================================================
# TITAN OS | MAIN KERNEL
# Integrates Telegram Bot + Web Dashboard + Video Streaming
# =========================================================

import sys
import os
import asyncio
import importlib
import logging
from threading import Thread
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, send_file, Response
from pyrogram import idle

# ---------------------------------------------------------
# 1. إعدادات السيرفر والمسارات
# ---------------------------------------------------------
# جعل مجلد القوالب هو المجلد الحالي لقراءة dashboard.html
app = Flask(__name__, template_folder=".", static_folder=".")
app.secret_key = "Titan_God_Mode_2025"

# إخفاء لوجات فلاسك المزعجة
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# بيانات دخول لوحة التحكم
ADMIN_USER = "Abdallah"
ADMIN_PASS = "asdfghjkl05896"

# ---------------------------------------------------------
# 2. استيراد مكاتب البوت (AnnieXMedia)
# ---------------------------------------------------------
try:
    sys.path.insert(0, os.getcwd())
    import config
    from AnnieXMedia import LOGGER, app as bot_app, userbot
    from AnnieXMedia.core.call import StreamController
    from AnnieXMedia.misc import sudo, db
    from AnnieXMedia.plugins import ALL_MODULES
    from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
except ImportError:
    print("CRITICAL: AnnieXMedia modules not found. Ensure you are in the root directory.")
    sys.exit(1)

# ---------------------------------------------------------
# 3. مسارات الموقع (Web Routes)
# ---------------------------------------------------------

@app.route('/')
def home():
    if session.get('user') == ADMIN_USER:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
            session['user'] = ADMIN_USER
            return redirect(url_for('dashboard'))
        return "<h1>Wrong Password!</h1>"
    
    # صفحة تسجيل دخول بسيطة جداً مدمجة
    return """
    <body style="background:#000; color:#fff; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;">
        <form method="post" style="text-align:center;">
            <h2 style="color:#0A84FF;">TITAN OS LOGIN</h2>
            <input type="text" name="username" placeholder="Username" style="padding:10px; border-radius:10px; border:none; display:block; margin:10px auto;">
            <input type="password" name="password" placeholder="Password" style="padding:10px; border-radius:10px; border:none; display:block; margin:10px auto;">
            <button style="padding:10px 20px; background:#0A84FF; color:#fff; border:none; border-radius:10px; cursor:pointer;">ACCESS</button>
        </form>
    </body>
    """

@app.route('/dashboard')
def dashboard():
    if not session.get('user'): return redirect(url_for('login_page'))
    # يقرأ ملف dashboard.html الموجود بجانب الملف
    if os.path.exists("dashboard.html"):
        return send_file("dashboard.html")
    return "<h1>Error: dashboard.html not found!</h1>"

@app.route('/logs')
def view_logs():
    if not session.get('user'): return "Access Denied"
    log_file = "log.txt" # تأكد من اسم ملف اللوج
    if os.path.exists(log_file):
        return send_file(log_file, mimetype="text/plain")
    return "No logs found."

# ---------------------------------------------------------
# 4. مسار تشغيل الفيديو (Video Stream Bridge)
# ---------------------------------------------------------
@app.route('/stream/<int:chat_id>')
def stream_video(chat_id):
    if not session.get('user'): return "Access Denied", 403
    
    # البحث عن مسار الملف في قاعدة البيانات
    if chat_id in db and db[chat_id]:
        track = db[chat_id][0]
        file_path = track.get("file")
        if file_path and os.path.exists(file_path):
            return send_file(file_path)
    
    return "No active stream found", 404

# ---------------------------------------------------------
# 5. الـ API (المحرك الذكي)
# ---------------------------------------------------------

# أ) جلب الجروبات النشطة
@app.route('/api/active_calls')
def api_active_calls():
    if not session.get('user'): return jsonify({"error": "Auth required"}), 401
    
    active_data = []
    
    async def get_chats_async():
        results = []
        try:
            # الحصول على قائمة الـ IDs من StreamController
            # (تختلف التسمية حسب نسخة السورس، نجرب الأكثر شيوعاً)
            call_ids = []
            if hasattr(StreamController, 'active_calls'):
                call_ids = list(StreamController.active_calls)
            elif hasattr(StreamController, 'call_py'):
                call_ids = StreamController.call_py.active_calls
            
            for chat_id in call_ids:
                chat_name = f"Chat {chat_id}"
                try:
                    chat = await bot_app.get_chat(chat_id)
                    chat_name = chat.title
                except: pass
                
                results.append({"id": chat_id, "name": chat_name})
        except Exception as e:
            print(f"Error scanning chats: {e}")
        return results

    try:
        future = asyncio.run_coroutine_threadsafe(get_chats_async(), bot_app.loop)
        active_data = future.result()
    except: pass

    return jsonify({"chats": active_data})

# ب) معلومات التراك (للواجهة)
@app.route('/api/track_info/<int:chat_id>')
def api_track_info(chat_id):
    if not session.get('user'): return jsonify({}), 401
    
    info = {"title": "Idle", "artist": "", "cover": "", "stream_url": ""}
    
    if chat_id in db and db[chat_id]:
        track = db[chat_id][0]
        vidid = track.get("vidid")
        cover_url = f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg" if vidid else "https://telegra.ph/file/6298d377ad3eb46711644.jpg"
        
        info = {
            "title": track.get("title", "Unknown"),
            "artist": track.get("by", "Unknown"),
            "cover": cover_url,
            "stream_url": f"/stream/{chat_id}"
        }
    return jsonify(info)

# ج) التحكم (Play/Pause/Skip/Turbo)
@app.route('/api/<cmd>/<chat_id>', methods=['POST'])
@app.route('/api/system/<cmd>', methods=['POST']) # للتيربو والكاش
def api_command(cmd, chat_id=None):
    if not session.get('user'): return jsonify({"ok": False}), 401

    async def execute_bot_command():
        try:
            # أوامر النظام
            if cmd == 'turbo':
                import gc
                gc.collect()
                return True
            if cmd == 'cleancache':
                os.system("rm -rf downloads/ cache/")
                return True
            
            # أوامر التشغيل
            cid = int(chat_id)
            if cmd == 'pause':
                await StreamController.pause_stream(cid)
            elif cmd == 'resume':
                await StreamController.resume_stream(cid)
            elif cmd in ['skip', 'stop']:
                await StreamController.stop_stream(cid)
            elif cmd == 'seek_back':
                # منطق الـ Seek يعتمد على السورس، سنقوم بإعادة التشغيل كمثال
                pass 
                
        except Exception as e:
            print(f"Cmd Error: {e}")

    try:
        asyncio.run_coroutine_threadsafe(execute_bot_command(), bot_app.loop).result()
        return jsonify({"ok": True})
    except:
        return jsonify({"ok": False})

# ---------------------------------------------------------
# 6. التشغيل (Boot Sequence)
# ---------------------------------------------------------
def run_flask_server():
    # تشغيل السيرفر على بورت 8080
    app.run(host="0.0.0.0", port=8080, use_reloader=False, threaded=True)

async def main_init():
    # 1. تشغيل الويب في Thread منفصل
    server_thread = Thread(target=run_flask_server)
    server_thread.daemon = True
    server_thread.start()
    
    LOGGER("TitanOS").info("✅ DASHBOARD STARTED: http://Your-IP:8080")

    # 2. تشغيل البوت
    if not config.STRING1:
        LOGGER(__name__).error("No Session String found!")
        return

    await sudo()
    try: await fetch_and_store_cookies()
    except: pass

    await bot_app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("AnnieXMedia.plugins" + all_module)

    await userbot.start()
    await StreamController.start()
    
    # 3. تفعيل الديكوريتورز (مهم لعمل الأوامر)
    try:
        await StreamController.decorators()
    except: pass

    LOGGER("AnnieXMedia").info("🔥 TITAN OS FULLY OPERATIONAL 🔥")
    await idle()

if __name__ == "__main__":
    # إنشاء الـ Loop وتشغيل كل شيء
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main_init())
