import os
import time
import shutil
import hashlib
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
    is_safe_file,
    logger,
    APIResponse,
    format_duration
)

# =========================================================
# 1. فئة إدارة الخزنة (Vault Manager Class)
# =========================================================
class VaultManager:
    """
    فئة مسؤولة عن كل عمليات نظام الملفات.
    """
    ROOT = Config.DOWNLOADS_DIR

    @staticmethod
    def scan_files(sort_by='date', filter_type='all'):
        """مسح المجلد وإرجاع قائمة الملفات"""
        files_list = []
        
        if not os.path.exists(VaultManager.ROOT):
            os.makedirs(VaultManager.ROOT)

        with os.scandir(VaultManager.ROOT) as entries:
            for entry in entries:
                if entry.is_file():
                    try:
                        stat = entry.stat()
                        name = entry.name
                        ext = os.path.splitext(name)[1].lower()
                        
                        # تحديد نوع الملف
                        ftype = 'unknown'
                        if ext in Config.ALLOWED_EXTENSIONS['video']: ftype = 'video'
                        elif ext in Config.ALLOWED_EXTENSIONS['audio']: ftype = 'audio'
                        
                        # الفلترة
                        if filter_type != 'all' and ftype != filter_type:
                            continue
                        
                        # تجميع البيانات
                        files_list.append({
                            "name": name,
                            "type": ftype,
                            "ext": ext,
                            "size_raw": stat.st_size,
                            "size": get_readable_size(stat.st_size),
                            "ctime": stat.st_ctime,
                            "mtime": stat.st_mtime,
                            "date": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                            "path": entry.path,
                            "hash": "" # الهاش تقيل فمش هنحسبه هنا
                        })
                    except Exception as e:
                        logger.error(f"Error scanning file {entry.name}", e)

        # الترتيب
        reverse = True
        if sort_by == 'name':
            files_list.sort(key=lambda x: x['name'].lower(), reverse=False)
        elif sort_by == 'size':
            files_list.sort(key=lambda x: x['size_raw'], reverse=True)
        else: # date
            files_list.sort(key=lambda x: x['mtime'], reverse=True)

        return files_list

    @staticmethod
    def get_stats():
        """حساب إحصائيات المساحة"""
        total_size = 0
        counts = {'audio': 0, 'video': 0, 'other': 0}
        
        for root, _, files in os.walk(VaultManager.ROOT):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total_size += os.path.getsize(fp)
                    ext = os.path.splitext(f)[1].lower()
                    if ext in Config.ALLOWED_EXTENSIONS['audio']: counts['audio'] += 1
                    elif ext in Config.ALLOWED_EXTENSIONS['video']: counts['video'] += 1
                    else: counts['other'] += 1
                except: pass
        
        usage = shutil.disk_usage(VaultManager.ROOT)
        return {
            "used_vault": get_readable_size(total_size),
            "used_raw": total_size,
            "disk_total": get_readable_size(usage.total),
            "disk_free": get_readable_size(usage.free),
            "disk_used": get_readable_size(usage.used),
            "files_count": counts
        }

    @staticmethod
    def get_unique_name(filename):
        """ضمان عدم تكرار الاسم"""
        if not os.path.exists(os.path.join(VaultManager.ROOT, filename)):
            return filename
        
        base, ext = os.path.splitext(filename)
        counter = 1
        while True:
            new_name = f"{base}_{counter}{ext}"
            if not os.path.exists(os.path.join(VaultManager.ROOT, new_name)):
                return new_name
            counter += 1

# =========================================================
# 2. فئة معالجة الوسائط (Media Converter - FFmpeg)
# =========================================================
class MediaProcessor:
    """
    غلاف لـ FFmpeg للتحويل والمعالجة.
    """
    @staticmethod
    def convert_to_mp3(input_path):
        if not os.path.exists(input_path): return False, "File not found"
        
        output_path = os.path.splitext(input_path)[0] + ".mp3"
        
        # أمر التحويل: استخراج الصوت بأعلى جودة
        cmd = [
            'ffmpeg', '-y', 
            '-i', input_path,
            '-vn', # لا فيديو
            '-acodec', 'libmp3lame',
            '-q:a', '2', # جودة عالية VBR
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, output_path
        except subprocess.CalledProcessError:
            return False, "FFmpeg conversion failed"
        except FileNotFoundError:
            return False, "FFmpeg not installed on server"

# =========================================================
# 3. واجهات العرض (View Endpoints)
# =========================================================

@web_bp.route('/api/vault/list')
def api_list_files():
    """عرض الملفات JSON"""
    sort = request.args.get('sort', 'date')
    ftype = request.args.get('type', 'all')
    
    files = VaultManager.scan_files(sort, ftype)
    return jsonify({"count": len(files), "files": files})

@web_bp.route('/api/vault/stats')
def api_vault_stats():
    """عرض الإحصائيات"""
    return jsonify(VaultManager.get_stats())

# =========================================================
# 4. واجهات الرفع (Upload Endpoints)
# =========================================================

@web_bp.route('/api/vault/upload', methods=['POST'])
@sudo_required
def api_upload():
    """
    رفع الملفات (يدعم الملفات الكبيرة والأسماء العربية).
    """
    if 'file' not in request.files:
        return APIResponse.error("No file part")
        
    file = request.files['file']
    if file.filename == '':
        return APIResponse.error("No selected file")

    # التحقق من النوع
    if not is_safe_file(file.filename):
        return APIResponse.error("File type not allowed (Audio/Video only)")

    try:
        # تأمين الاسم
        original_name = file.filename
        safe_name = secure_filename(original_name)
        
        # حل مشكلة secure_filename مع العربي (بيرجع فاضي)
        if not safe_name:
            safe_name = f"upload_{int(time.time())}{os.path.splitext(original_name)[1]}"
            
        # منع التكرار
        final_name = VaultManager.get_unique_name(safe_name)
        save_path = os.path.join(VaultManager.ROOT, final_name)

        # الحفظ (chunked write عشان الرامات)
        file.save(save_path)
        
        log_activity("UPLOAD", f"File: {final_name}")
        return APIResponse.success({
            "filename": final_name, 
            "size": get_readable_size(os.path.getsize(save_path))
        })
        
    except Exception as e:
        logger.error("Upload Failed", e)
        return APIResponse.error("Server upload error", details=e)

# =========================================================
# 5. واجهات التحكم (Actions: Play, Delete, Convert)
# =========================================================

@web_bp.route('/api/vault/action', methods=['POST'])
@sudo_required
def api_file_action():
    data = request.json
    action = data.get('action')
    filename = data.get('filename')
    
    if not filename: return APIResponse.error("Filename required")
    
    file_path = os.path.join(VaultManager.ROOT, filename)
    if not os.path.exists(file_path):
        return APIResponse.error("File not found on server", 404)

    try:
        # --- حذف ---
        if action == 'delete':
            os.remove(file_path)
            log_activity("DELETE_FILE", filename)
            return APIResponse.success(message="File deleted permanently")

        # --- تشغيل ---
        elif action == 'play':
            run_async(StreamController.stream_call(file_path))
            log_activity("PLAY_LOCAL", filename)
            return APIResponse.success(message="Streaming started")

        # --- إعادة تسمية ---
        elif action == 'rename':
            new_name = secure_filename(data.get('new_name'))
            if not new_name: return APIResponse.error("Invalid new name")
            
            # الحفاظ على الامتداد
            ext = os.path.splitext(filename)[1]
            if not new_name.endswith(ext): new_name += ext
            
            new_path = os.path.join(VaultManager.ROOT, new_name)
            os.rename(file_path, new_path)
            return APIResponse.success(message=f"Renamed to {new_name}")

        # --- تحويل ---
        elif action == 'convert':
            # تشغيل في الخلفية (Thread/Process)
            def bg_convert():
                success, msg = MediaProcessor.convert_to_mp3(file_path)
                if success: logger.info(f"Conversion Done: {filename}")
                else: logger.error(f"Conversion Failed: {msg}")
            
            import threading
            threading.Thread(target=bg_convert).start()
            
            return APIResponse.success(message="Conversion started in background")

    except Exception as e:
        return APIResponse.error("Action failed", details=e)

    return APIResponse.error("Unknown action")

@web_bp.route('/vault/dl/<path:filename>')
def download_serve(filename):
    """رابط تحميل مباشر"""
    return send_from_directory(Config.DOWNLOADS_DIR, filename, as_attachment=True)
