import os
import time
import shutil
import subprocess
from datetime import datetime
from flask import jsonify, request, send_from_directory, current_app
from werkzeug.utils import secure_filename
from . import web_bp
from .utils import (
    Config, 
    run_async, 
    StreamController, 
    get_readable_size, 
    sudo_required, 
    log_activity,
    is_safe_file
)

# =========================================================
# 1. إعدادات الرفع (Upload Config)
# =========================================================
# دالة لضمان عدم تكرار الأسماء
def get_unique_filename(directory, filename):
    base, ext = os.path.splitext(filename)
    counter = 1
    new_filename = filename
    while os.path.exists(os.path.join(directory, new_filename)):
        new_filename = f"{base}_{counter}{ext}"
        counter += 1
    return new_filename

# =========================================================
# 2. مستكشف الملفات
# =========================================================
@web_bp.route('/api/vault/list')
def list_vault_files():
    if not os.path.exists(Config.DOWNLOADS_DIR):
        os.makedirs(Config.DOWNLOADS_DIR)

    sort_by = request.args.get('sort', 'date')
    file_type = request.args.get('type', 'all')
    files_data = []
    
    with os.scandir(Config.DOWNLOADS_DIR) as entries:
        for entry in entries:
            if entry.is_file(): # شيلنا is_safe_file هنا عشان نشوف كل حاجة ونمسح الغلط
                try:
                    stat = entry.stat()
                    ext = os.path.splitext(entry.name)[1].lower()
                    f_type = "video" if ext in ['.mp4', '.mkv', '.webm'] else "audio"
                    
                    if file_type != 'all' and f_type != file_type: continue

                    files_data.append({
                        "name": entry.name,
                        "type": f_type,
                        "size": get_readable_size(stat.st_size),
                        "date": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                        "path": entry.path
                    })
                except: pass

    # الترتيب
    if sort_by == 'size': files_data.sort(key=lambda x: x.get('size', 0), reverse=True)
    else: files_data.sort(key=lambda x: x.get('date', ''), reverse=True)

    return jsonify({"files": files_data})

# =========================================================
# 3. إحصائيات
# =========================================================
@web_bp.route('/api/vault/stats')
def vault_stats():
    total_size = 0
    count = 0
    for root, _, files in os.walk(Config.DOWNLOADS_DIR):
        for f in files:
            try: total_size += os.path.getsize(os.path.join(root, f))
            except: pass
            count += 1
            
    total, used, free = shutil.disk_usage(Config.DOWNLOADS_DIR)
    return jsonify({
        "vault_size": get_readable_size(total_size),
        "disk_free": get_readable_size(free),
        "count": count
    })

# =========================================================
# 4. الرفع الحقيقي (The Real Upload Handler) 🚀
# =========================================================
@web_bp.route('/api/vault/upload', methods=['POST'])
@sudo_required
def upload_file():
    """
    نظام رفع قوي يدعم الملفات الكبيرة والأسماء العربية
    """
    # 1. التأكد من وجود الملف
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file part sent"}), 400
        
    file = request.files['file']
    
    # 2. التأكد من اختيار ملف
    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400

    # 3. التحقق من الامتداد (Audio/Video Only)
    if not is_safe_file(file.filename):
        return jsonify({"success": False, "error": "Format not supported (Audio/Video only)"}), 400

    try:
        # 4. معالجة الاسم (تأمين + دعم عربي بسيط + منع التكرار)
        original_name = file.filename
        # secure_filename أحياناً بتبوظ العربي، فلو الاسم فضي نستخدم timestamp
        safe_name = secure_filename(original_name)
        if not safe_name: 
            safe_name = f"upload_{int(time.time())}{os.path.splitext(original_name)[1]}"
            
        final_name = get_unique_filename(Config.DOWNLOADS_DIR, safe_name)
        save_path = os.path.join(Config.DOWNLOADS_DIR, final_name)

        # 5. الحفظ (Streaming Save) عشان مياكلش الرام
        file.save(save_path)
        
        log_activity("UPLOAD_SUCCESS", f"File: {final_name} | Size: {get_readable_size(os.path.getsize(save_path))}")
        
        return jsonify({
            "success": True, 
            "message": "Upload Complete", 
            "filename": final_name
        })
        
    except Exception as e:
        log_activity("UPLOAD_ERROR", str(e))
        return jsonify({"success": False, "error": f"Server Error: {str(e)}"}), 500

# =========================================================
# 5. باقي الأوامر (Delete, Play, Convert)
# =========================================================
@web_bp.route('/api/vault/action', methods=['POST'])
@sudo_required
def handle_vault_action():
    data = request.json
    action = data.get('action')
    filename = data.get('filename')
    path = os.path.join(Config.DOWNLOADS_DIR, filename)
    
    if not os.path.exists(path): return jsonify({"error": "File lost"})

    if action == 'delete':
        os.remove(path)
        return jsonify({"success": True})
        
    elif action == 'play':
        run_async(StreamController.stream_call(path))
        return jsonify({"success": True})

    elif action == 'rename':
        new_name = secure_filename(data.get('new_name'))
        if not new_name: return jsonify({"error": "Invalid name"})
        os.rename(path, os.path.join(Config.DOWNLOADS_DIR, new_name))
        return jsonify({"success": True})
        
    elif action == 'convert':
        # تحويل سريع لـ MP3
        if not filename.endswith(('mp4','mkv')): return jsonify({"error": "Video only"})
        new_file = os.path.splitext(path)[0] + ".mp3"
        subprocess.Popen(f'ffmpeg -i "{path}" -vn -ab 128k "{new_file}" -y', shell=True)
        return jsonify({"success": True, "message": "Conversion started in background"})

    return jsonify({"success": False})

@web_bp.route('/vault/dl/<path:filename>')
def download_local(filename):
    return send_from_directory(Config.DOWNLOADS_DIR, filename, as_attachment=True)
