import os
import time
import psutil
import subprocess
import asyncio
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request
from AnnieXMedia.core.call import StreamController

# تعريف البلوبرينت
web_bp = Blueprint('web', __name__, template_folder='templates', static_folder='static')

DOWNLOADS_DIR = "downloads"
START_TIME = time.time() # لحساب وقت التشغيل (Uptime)

# --- دوال مساعدة ---
def get_size(bytes, suffix="B"):
    """تحويل الحجم لصيغة مقروءة"""
    factor = 1024
    for unit in ["", "K", "M", "G", "T", "P"]:
        if bytes < factor:
            return f"{bytes:.2f}{unit}{suffix}"
        bytes /= factor

# --- الراوتات الأساسية ---
@web_bp.route('/')
def home():
    return render_template('index.html')

# --- 1. API: حالة النظام والمراقبة (System Monitor) ---
@web_bp.route('/api/system')
def system_stats():
    # 1. المعالج
    cpu_usage = psutil.cpu_percent(interval=None)
    
    # 2. الرامات
    svmem = psutil.virtual_memory()
    ram_usage = svmem.percent
    ram_total = get_size(svmem.total)
    
    # 3. الهارد ديسك
    disk = psutil.disk_usage('/')
    disk_usage = disk.percent
    
    # 4. وقت التشغيل
    uptime_seconds = int(time.time() - START_TIME)
    uptime = str(datetime.utcfromtimestamp(uptime_seconds).strftime('%H:%M:%S'))

    return jsonify({
        "cpu": cpu_usage,
        "ram": ram_usage,
        "ram_txt": f"{get_size(svmem.used)} / {ram_total}",
        "disk": disk_usage,
        "uptime": uptime,
        "ping": f"{round(psutil.net_io_counters().bytes_sent / 1024 / 1024, 2)} MB Sent"
    })

# --- 2. API: التحكم في المشغل (Player Bridge) ---
@web_bp.route('/api/status')
def get_status():
    # هنا المفروض نربط مع متغيرات البوت الحقيقية
    # حالياً بنرجع بيانات وهمية للتجربة لحد ما نربط الـ Queue
    return jsonify({
        "status": "playing",
        "track": "DashX Ultimate System", 
        "artist": "System Active",
        "cover": "https://telegra.ph/file/8b3e21894d3062325c04b.jpg",
        "position": int(time.time() % 300), 
        "duration": 300, 
        "listeners": 5, 
        "ping": "Live"
    })

@web_bp.route('/api/control', methods=['POST'])
def control_player():
    try:
        data = request.json
        action = data.get('action')
        chat_id = data.get('chat_id')
        
        loop = asyncio.get_event_loop()
        
        if action == 'pause':
            loop.create_task(StreamController.pause_stream(chat_id))
        elif action == 'resume':
            loop.create_task(StreamController.resume_stream(chat_id))
        elif action == 'skip':
            loop.create_task(StreamController.skip_stream(chat_id))
            
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# --- 3. API: الخزنة (The Vault) ---
@web_bp.route('/api/vault/list')
def list_files():
    if not os.path.exists(DOWNLOADS_DIR): os.makedirs(DOWNLOADS_DIR)
    files_data = []
    for filename in os.listdir(DOWNLOADS_DIR):
        if filename.lower().endswith(('.mp3', '.m4a', '.mp4', '.mkv')):
            path = os.path.join(DOWNLOADS_DIR, filename)
            try:
                stat = os.stat(path)
                size_mb = stat.st_size / (1024 * 1024)
                mod_time = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                files_data.append({
                    "name": filename,
                    "type": "video" if filename.endswith(('.mp4', '.mkv')) else "audio",
                    "size": f"{size_mb:.1f} MB", "date": mod_time, "path": path
                })
            except: pass
    return jsonify({"files": files_data})

@web_bp.route('/api/vault/action', methods=['POST'])
def vault_action():
    data = request.json
    action = data.get('action')
    filename = data.get('filename')
    path = os.path.join(DOWNLOADS_DIR, filename)
    
    if not os.path.exists(path): return jsonify({"success": False})

    if action == 'play':
        loop = asyncio.get_event_loop()
        loop.create_task(StreamController.stream_call(path))
        return jsonify({"success": True})
    elif action == 'delete':
        os.remove(path)
        return jsonify({"success": True})
    
    return jsonify({"success": False})

# --- 4. API: الطرفية (Sudo Terminal) ---
@web_bp.route('/api/terminal', methods=['POST'])
def run_terminal():
    """تنفيذ أوامر النظام من الموقع مباشرة (Sudo Only)"""
    command = request.json.get('command')
    if not command: return jsonify({"output": ""})
    
    # حماية بسيطة (منع الأوامر المدمرة)
    if command.strip() in ['rm -rf /', 'reboot', 'shutdown']:
         return jsonify({"output": "❌ Command Blocked by Safety Protocol"})

    try:
        # تنفيذ الأمر
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
        return jsonify({"output": result.decode('utf-8')})
    except subprocess.CalledProcessError as e:
        return jsonify({"output": e.output.decode('utf-8')})
    except Exception as e:
        return jsonify({"output": str(e)})
