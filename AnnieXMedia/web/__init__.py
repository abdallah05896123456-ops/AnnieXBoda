
# ==============================
# 4. API: نظام الخزنة (The Vault)
# ==============================

DOWNLOADS_DIR = "downloads"  # اسم الفولدر اللي هنعرض ملفاته

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

@web_bp.route('/api/vault/list')
def list_files():
    """جلب قائمة الملفات الموجودة"""
    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR) # لو الفولدر مش موجود نعمله
        
    files_data = []
    
    # قراءة الملفات
    for filename in os.listdir(DOWNLOADS_DIR):
        # بنعرض بس ملفات الصوت والفيديو
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
    chat_id = data.get('chat_id')
    
    path = os.path.join(DOWNLOADS_DIR, filename)
    
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "File not found"})

    try:
        if action == 'play':
            # أمر التشغيل المباشر للملف المحلي
            loop = asyncio.get_event_loop()
            loop.create_task(StreamController.stream_call(path)) # تأكد إن دي دالة التشغيل عندك
            return jsonify({"success": True, "message": "Playing now..."})
            
        elif action == 'delete':
            os.remove(path)
            return jsonify({"success": True, "message": "Deleted successfully"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
        
    return jsonify({"success": False})
