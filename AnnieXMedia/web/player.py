import time
import asyncio
import logging
from datetime import datetime, timedelta
from flask import jsonify, request, session
from . import web_bp
from .utils import (
    run_async, 
    StreamController, 
    db, 
    sudo_required, 
    format_duration, 
    log_activity
)

logger = logging.getLogger("DashX_Player")

# =========================================================
# بيانات وهمية متقدمة (Advanced Mock Data)
# =========================================================
# لاحظ حقل 'user_img' عشان طلبك
MOCK_CHATS = [
    {
        "chat_id": -100123456789,
        "title": "سهرة ملوك البرمجة 👑",
        "track": "Ahmed Mekky - Atr Al Hayah",
        "cover": "https://telegra.ph/file/8b3e21894d3062325c04b.jpg",
        "user": "Ahmed",
        "user_img": "https://telegra.ph/file/5a5d09854728704253158.jpg",
        "duration": 245,
        "position": 120,
        "listeners": 15,
        "active": True
    },
    {
        "chat_id": -100987654321,
        "title": "Music Galaxy 🎵",
        "track": "Alan Walker - Faded",
        "cover": "https://i1.sndcdn.com/artworks-000185747619-j1z80j-t500x500.jpg",
        "user": "Sarah",
        "user_img": "https://telegra.ph/file/710609b5527a20c327293.jpg",
        "duration": 300,
        "position": 45,
        "listeners": 42,
        "active": True
    }
]

# =========================================================
# 1. لوحة المعلومات (Dashboard API)
# =========================================================
@web_bp.route('/api/player/dashboard')
def dashboard_data():
    """المحرك الذكي: يقرر عرض الرامات أو الجروبات"""
    try:
        # هنا مفروض تجيب الداتا من StreamController
        # active_chats = run_async(StreamController.get_active_chats())
        active_chats = [] # خليه فاضي حاليا عشان نستخدم الموك

        if not active_chats:
            active_chats = MOCK_CHATS

        # لو مفيش خالص -> وضع السكون
        if not active_chats:
            return jsonify({
                "mode": "stats",
                "message": "لـيـس هـنـاك اغـنـيـة تـعـمـل الان",
                "sub_message": "النظام في وضع الاستعداد"
            })
        
        # تحديث شريط التقدم وهمياً
        for chat in active_chats:
            chat['position'] += 3
            if chat['position'] > chat['duration']: chat['position'] = 0
            chat['progress'] = (chat['position'] / chat['duration']) * 100
            chat['position_str'] = format_duration(chat['position'])

        return jsonify({
            "mode": "active",
            "chats": active_chats
        })

    except Exception as e:
        logger.error(f"Dash Error: {e}")
        return jsonify({"mode": "error", "message": str(e)})

# =========================================================
# 2. التحكم في المجموعات (Modal Actions)
# =========================================================
@web_bp.route('/api/player/group_action', methods=['POST'])
@sudo_required
def group_action():
    data = request.json
    action = data.get('action')
    chat_id = data.get('chat_id')

    if not chat_id: return jsonify({"success": False, "msg": "Chat ID Missing"})

    log_activity(f"GROUP_{action.upper()}", f"Chat: {chat_id}")

    try:
        if action == 'stop':
            if StreamController: run_async(StreamController.stop_stream(chat_id))
            global MOCK_CHATS
            MOCK_CHATS = [c for c in MOCK_CHATS if c['chat_id'] != chat_id]
            return jsonify({"success": True, "msg": "تم الإيقاف بنجاح"})
            
        elif action == 'ban':
            if db: db.blacklist.insert_one({"chat_id": chat_id, "date": datetime.now()})
            return jsonify({"success": True, "msg": "تم حظر المجموعة ⛔"})
            
        elif action == 'focus':
            return jsonify({"success": True, "msg": "تم توجيه الموارد 🚀"})

        elif action == 'pause':
            if StreamController: run_async(StreamController.pause_stream(chat_id))
            return jsonify({"success": True, "msg": "تم الإيقاف المؤقت"})
            
        elif action == 'resume':
            if StreamController: run_async(StreamController.resume_stream(chat_id))
            return jsonify({"success": True, "msg": "تم الاستئناف"})

        elif action == 'skip':
            if StreamController: run_async(StreamController.skip_stream(chat_id))
            return jsonify({"success": True, "msg": "تم التخطي"})

    except Exception as e:
        return jsonify({"success": False, "msg": f"خطأ: {str(e)}"})
    
    return jsonify({"success": False, "msg": "أمر غير معروف"})

# =========================================================
# 3. التحكم والبحث (Direct Controls)
# =========================================================
@web_bp.route('/api/player/play', methods=['POST'])
@sudo_required
def play_direct():
    data = request.json
    url = data.get('url')
    chat_id = data.get('chat_id')
    if not url: return jsonify({"error": "No URL"})
    
    try:
        run_async(StreamController.play_stream(chat_id, url))
        return jsonify({"success": True, "msg": "Playing..."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
