# Authored By Certified Coders © 2025
import asyncio
import os
import logging
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for

# استيراد أدوات التحكم من البوت
from AnnieXMedia.core.call import StreamController
from AnnieXMedia import app as bot_app
from config import WEB_PASSWORD

# استيراد أدوات الداتابيز (بأمان عشان لو فيه ملف ناقص ميعطلش الدنيا)
try:
    from AnnieXMedia.utils.database import get_active_chats, remove_active_chat
except ImportError:
    def get_active_chats(): return []
    def remove_active_chat(chat_id): pass

web_bp = Blueprint('web', __name__)
logger = logging.getLogger("WebDashboard")

# --- الجسر بين الموقع والبوت (Async Bridge) ---
def run_async(coro):
    """تشغيل أوامر البوت الـ Async داخل بيئة Flask"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, loop)
    except Exception as e:
        logger.error(f"Async Error: {e}")
    return None

# --- التحقق من تسجيل الدخول ---
def is_auth():
    return session.get('authenticated', False)

# --- صفحات تسجيل الدخول ---
@web_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == WEB_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('web.dashboard'))
        return render_template('index.html', error="كلمة المرور غير صحيحة", login_page=True)
    return render_template('index.html', login_page=True)

@web_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('web.login'))

# --- الصفحة الرئيسية (الداشبورد) ---
@web_bp.route('/')
def dashboard():
    if not is_auth(): return redirect(url_for('web.login'))
    return render_template('index.html', login_page=False)

# --- APIs: جلب المعلومات والتحكم ---

@web_bp.route('/api/stats')
def stats():
    if not is_auth(): return jsonify({"error": "Unauthorized"}), 403
    
    chats = get_active_chats()
    active_data = []
    
    # تجهيز بيانات الجروبات الشغالة
    for c in chats:
        try:
            cid = c['chat_id'] if isinstance(c, dict) else c
            active_data.append({
                "id": cid,
                "name": f"Group {str(cid)[4:]}.."  # اخفاء جزء من الايدي للشكل
            })
        except: pass
        
    return jsonify({
        "cpu": f"{os.cpu_count()} Cores",
        "active_calls": len(active_data),
        "chats": active_data
    })

@web_bp.route('/api/action', methods=['POST'])
def action():
    if not is_auth(): return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    cmd = data.get('cmd')
    chat_id = int(data.get('chat_id'))
    
    try:
        if cmd == 'pause':
            run_async(StreamController.pause_stream(chat_id))
        elif cmd == 'resume':
            run_async(StreamController.resume_stream(chat_id))
        elif cmd == 'mute':
            run_async(StreamController.mute_stream(chat_id))
        elif cmd == 'unmute':
            run_async(StreamController.unmute_stream(chat_id))
        elif cmd == 'skip':
            # التخطي هنا بيعمل إيقاف إجباري، والبوت أوتوماتيك بيشغل اللي بعده في القائمة
            run_async(StreamController.force_stop_stream(chat_id))
        elif cmd == 'stop':
            run_async(StreamController.force_stop_stream(chat_id))
            try: remove_active_chat(chat_id)
            except: pass
            
        return jsonify({"status": "ok", "msg": f"تم تنفيذ الأمر: {cmd}"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@web_bp.route('/api/remote_play', methods=['POST'])
def remote_play():
    if not is_auth(): return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    chat_id = int(data.get('chat_id'))
    query = data.get('query')
    
    if not chat_id or not query: return jsonify({"status": "error"})
    
    # ارسال امر التشغيل للجروب كأن يوزر كتبه
    async def _send():
        await bot_app.send_message(chat_id, f"/play {query}")
        
    run_async(_send())
    return jsonify({"status": "ok", "msg": "تم إرسال الأمر للجروب"})
