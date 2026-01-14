import os
import asyncio
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request

# استيراد كائنات البوت (تأكد من المسار حسب مشروعك)
from AnnieXMedia import app as bot_app
from AnnieXMedia.core.call import StreamController

# =========================================================
# 1. إنشاء الـ Blueprint (لازم يكون هنا في الأول)
# =========================================================
web_bp = Blueprint('web', __name__, template_folder='templates', static_folder='static')

# متغير لمسار التنزيلات
DOWNLOADS_DIR = "downloads"

# =========================================================
# 2. الدوال المساعدة
# =========================================================
def get_file_info(path):
    """دالة مساعدة بتجيب حجم الملف وتاريخه"""
    try:
        stat = os.stat(path)
        # تحويل الحجم لـ MB
        size_mb = stat.st_size / (1024 * 1024)
        # تحويل التاريخ لصيغة مقروءة
        mod_time = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
        return size_mb, mod_time
    except:
        return 0, "Unknown"

# =========================================================
# 3. الراوتات (Routes & APIs)
# =========================================================

@web_bp.route('/')
def home():
    """تحميل واجهة الـ Dashboard"""
    return render_template('index.html')

@web_bp.route('/api/status')
def get_status():
    """إرسال بيانات الأغنية الحالية للواجهة"""
    return jsonify({
        "status": "playing",
        "track": "AnnieX System Active", 
        "artist": "Waiting for commands...",
        "cover": "https://telegra.ph/file/8b3e21894d3062325c04b.jpg",
        "position": 0,
        "duration": 100,
        "listeners": 0,
        "ping": "Online"
    })

@web_bp.route('/api/control', methods=['POST'])
def control_player():
    """استقبال الأوامر من أزرار الموقع"""
    try:
        data = request.json
        action = data.get('action')
        chat_id = data.get('chat_id') 

        if not chat_id:
            return jsonify({"success": False, "error": "Chat ID Missing"})

        loop = asyncio.get_event_loop()

        if action == 'pause':
            loop.create_task(StreamController.pause_stream(chat_id))
        elif action == 'resume':
            loop.create_task(StreamController.resume_stream(chat_id))
        elif action == 'skip':
            loop.create_task(StreamController.skip_stream(chat_id))

        print(f"✅ Web Control: {action} -> {chat_id}")
        return jsonify({"success": True, "action": action})

    except Exception as e:
        print(f"❌ Web Error: {e}")
        return jsonify({"success": False, "error": str(e)})

# --- نظام الخزنة (The Vault) ---

@web_bp.route('/api/vault/list')
def list_files():
    """جلب قائمة الملفات الموجودة"""
    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR)
        
    files_data = []
    
    for filename in os.listdir(DOWNLOADS_DIR):
        if filename.lower().endswith(('.mp3', '.m4a', '.flac', '.mp4', '.mkv', '.webm')):
            path = os.path.join(DOWNLOADS_DIR, filename)
            size, date = get_file_info(path)
            
            files_data.append({
                "name": filename,
                "type": "video" if filename.endswith(('.mp4', '.mkv')) else "audio",
                "size": f"{size:.1f} MB",
                "date": date,
                "path": path
            })
    
    return jsonify({"files": files_data})

@web_bp.route('/api/vault/action', methods=['POST'])
def vault_action():
    """تشغيل أو حذف ملف"""
    data = request.json
    action = data.get('action')
    filename = data.get('filename')
    
    path = os.path.join(DOWNLOADS_DIR, filename)
    
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "File not found"})

    try:
        if action == 'play':
            loop = asyncio.get_event_loop()
            # تأكد أن stream_call تأخذ مسار الملف
            loop.create_task(StreamController.stream_call(path)) 
            return jsonify({"success": True, "message": "Playing now..."})
            
        elif action == 'delete':
            os.remove(path)
            return jsonify({"success": True, "message": "Deleted successfully"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
        
    return jsonify({"success": False})
