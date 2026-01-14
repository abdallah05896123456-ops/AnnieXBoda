import os
import asyncio
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request
from AnnieXMedia.core.call import StreamController

# تعريف البلوبرينت
web_bp = Blueprint('web', __name__, template_folder='templates', static_folder='static')

DOWNLOADS_DIR = "downloads"

# دوال مساعدة
def get_file_info(path):
    try:
        stat = os.stat(path)
        size_mb = stat.st_size / (1024 * 1024)
        mod_time = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
        return size_mb, mod_time
    except:
        return 0, "Unknown"

# الراوتات
@web_bp.route('/')
def home():
    return render_template('index.html')

@web_bp.route('/api/status')
def get_status():
    return jsonify({
        "status": "playing",
        "track": "AnnieX System", 
        "artist": "Ready",
        "cover": "https://telegra.ph/file/8b3e21894d3062325c04b.jpg",
        "position": 0, "duration": 0, "listeners": 0, "ping": "Online"
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

@web_bp.route('/api/vault/list')
def list_files():
    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR)
    files_data = []
    for filename in os.listdir(DOWNLOADS_DIR):
        if filename.lower().endswith(('.mp3', '.m4a', '.mp4', '.mkv')):
            path = os.path.join(DOWNLOADS_DIR, filename)
            size, date = get_file_info(path)
            files_data.append({
                "name": filename,
                "type": "video" if filename.endswith(('.mp4', '.mkv')) else "audio",
                "size": f"{size:.1f} MB", "date": date, "path": path
            })
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
