import time
import asyncio
import logging
import random
from datetime import datetime, timedelta
from flask import jsonify, request, session, current_app
from . import web_bp
from .utils import (
    run_async, 
    StreamController, 
    db, 
    sudo_required, 
    format_duration, 
    log_activity,
    CacheManager
)

# =========================================================
# 1. إعدادات السجلات والتهيئة (Setup & Logging)
# =========================================================
logger = logging.getLogger("DashX_Player")
logger.setLevel(logging.INFO)

# =========================================================
# 2. بيانات المحاكاة (Mock Data) - للطوارئ والتجربة
# =========================================================
# تم إضافة حقل 'user_img' عشان طلبك (صورة المستخدم جنب الأغنية)
MOCK_CHATS = [
    {
        "chat_id": -100123456789,
        "title": "سهرة ملوك البرمجة 👑",
        "track": "Ahmed Mekky - Atr Al Hayah",
        "cover": "https://telegra.ph/file/8b3e21894d3062325c04b.jpg",
        "user": "Ahmed",
        "user_img": "https://telegra.ph/file/5a5d09854728704253158.jpg", # صورة اليوزر
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
        "user_img": "https://telegra.ph/file/710609b5527a20c327293.jpg", # صورة اليوزر
        "duration": 300,
        "position": 45,
        "listeners": 42,
        "active": True
    }
]

# حالة المشغل الافتراضية
PLAYER_STATE = {
    "volume": 100,
    "speed": 1.0,
    "loop": False,
    "shuffle": False
}

# =========================================================
# 3. محرك لوحة القيادة (Dashboard Engine) 🧠
# =========================================================

@web_bp.route('/api/player/dashboard')
def dashboard_data():
    """
    عصب النظام: بيحدد نعرض الرامات ولا الجروبات.
    """
    try:
        # 1. محاولة جلب البيانات الحقيقية من الـ StreamController
        active_chats = []
        if StreamController:
            # tasks = run_async(StreamController.get_all_active_chats())
            # active_chats = parse_bot_data(tasks) 
            pass 
        
        # 2. استخدام الموك داتا لو مفيش اتصال (للتجربة)
        if not active_chats:
            active_chats = MOCK_CHATS

        # 3. منطق التبديل الذكي (Smart Switch)
        if not active_chats:
            return jsonify({
                "mode": "stats",
                "message": "لـيـس هـنـاك اغـنـيـة تـعـمـل الان",
                "sub_message": "السيرفر في وضع الاستعداد"
            })
        
        # تحديث شريط التقدم وهمياً للتجربة
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
        logger.error(f"Dashboard Error: {e}")
        return jsonify({"mode": "stats", "message": "System Error", "error": str(e)})

# =========================================================
# 4. التحكم في المجموعات (Group Actions Modal) 🎮
# =========================================================

@web_bp.route('/api/player/group_action', methods=['POST'])
@sudo_required
def group_action():
    """
    التحكم العميق: إيقاف، حظر، تركيز موارد.
    """
    data = request.json
    action = data.get('action')
    chat_id = data.get('chat_id')

    if not chat_id: return jsonify({"success": False, "msg": "Chat ID missing"})

    log_activity(f"GROUP_OP_{action.upper()}", f"Target: {chat_id}")

    try:
        # --- إيقاف التشغيل ---
        if action == 'stop':
            if StreamController:
                run_async(StreamController.stop_stream(chat_id))
            
            # تحديث الموك داتا للحذف الفوري (للتجربة)
            global MOCK_CHATS
            MOCK_CHATS = [c for c in MOCK_CHATS if c['chat_id'] != chat_id]
            
            return jsonify({"success": True, "msg": "تم إيقاف التشغيل بنجاح"})

        # --- حظر المجموعة ---
        elif action == 'ban':
            if db:
                db.blacklist.insert_one({
                    "chat_id": chat_id,
                    "reason": "Admin Ban via Dashboard",
                    "date": datetime.utcnow()
                })
            # هنا مفروض نطرد البوت من الجروب
            # run_async(StreamController.leave_chat(chat_id))
            return jsonify({"success": True, "msg": "⛔ تم حظر المجموعة وإيقاف الخدمة"})

        # --- تركيز الموارد (Focus Mode) ---
        elif action == 'focus':
            # ميزة حصرية: تقليل جودة المكالمات الأخرى ورفع جودة دي
            # run_async(StreamController.set_high_priority(chat_id))
            return jsonify({"success": True, "msg": "🚀 تم تحويل السيرفر لوضع التركيز"})

        # --- تخطي (Skip) من المودال ---
        elif action == 'skip':
            if StreamController:
                run_async(StreamController.skip_stream(chat_id))
            return jsonify({"success": True, "msg": "تم تخطي الأغنية"})

    except Exception as e:
        return jsonify({"success": False, "msg": f"فشل التنفيذ: {str(e)}"})
    
    return jsonify({"success": False, "msg": "أمر غير معروف"})

# =========================================================
# 5. التحكم الدقيق في المشغل (Fine Controls) 🎛️
# =========================================================

@web_bp.route('/api/player/control', methods=['POST'])
@sudo_required
def player_control():
    """
    Play, Pause, Volume, Seek, Speed
    """
    data = request.json
    action = data.get('action')
    chat_id = data.get('chat_id')
    value = data.get('value')

    try:
        if action == 'pause':
            run_async(StreamController.pause_stream(chat_id))
        elif action == 'resume':
            run_async(StreamController.resume_stream(chat_id))
        elif action == 'volume':
            # value: 0-200
            run_async(StreamController.set_volume(chat_id, int(value)))
            PLAYER_STATE['volume'] = int(value)
        elif action == 'speed':
            # value: 1.0, 1.5, 2.0
            run_async(StreamController.set_speed(chat_id, float(value)))
        elif action == 'seek':
            # value: seconds
            run_async(StreamController.seek_stream(chat_id, int(value)))

        return jsonify({"success": True, "state": PLAYER_STATE})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# =========================================================
# 6. التشغيل المباشر (Direct Play) ▶️
# =========================================================

@web_bp.route('/api/player/play', methods=['POST'])
@sudo_required
def play_track():
    """تشغيل رابط يوتيوب أو ملف مباشر"""
    data = request.json
    url = data.get('url')
    chat_id = data.get('chat_id')
    
    if not url or not chat_id:
        return jsonify({"error": "Missing URL or Chat ID"})

    try:
        # إضافة للموك داتا مؤقتاً للتجربة
        MOCK_CHATS.append({
            "chat_id": chat_id,
            "title": "تشغيل مباشر من الداشبورد",
            "track": "Loading...",
            "cover": "https://telegra.ph/file/8b3e21894d3062325c04b.jpg",
            "user": "Admin",
            "user_img": "https://telegra.ph/file/5a5d09854728704253158.jpg",
            "duration": 0, position: 0, listeners: 1, active: True
        })
        
        # الأمر الحقيقي
        run_async(StreamController.play_stream(chat_id, url))
        
        # تسجيل في الهستوري
        if db:
            db.history.insert_one({
                "chat_id": chat_id, 
                "url": url, 
                "date": datetime.utcnow()
            })
            
        return jsonify({"success": True, "msg": "Request sent to bot"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# =========================================================
# 7. إدارة طابور الانتظار (Queue System) 📋
# =========================================================

@web_bp.route('/api/player/queue')
def get_queue():
    chat_id = request.args.get('chat_id')
    # محاكاة
    queue = [
        {"title": "Track 1", "dur": "3:00", "user": "User A"},
        {"title": "Track 2", "dur": "4:20", "user": "User B"},
    ]
    return jsonify({"queue": queue})

@web_bp.route('/api/player/queue/clear', methods=['POST'])
@sudo_required
def clear_queue():
    chat_id = request.json.get('chat_id')
    run_async(StreamController.clear_queue(chat_id))
    return jsonify({"success": True})

# =========================================================
# 8. السجل والتاريخ (History) 📜
# =========================================================

@web_bp.route('/api/player/history')
def playback_history():
    if not db: return jsonify([])
    try:
        history = list(db.history.find().sort("date", -1).limit(50))
        for h in history: h['_id'] = str(h['_id'])
        return jsonify(history)
    except: return jsonify([])

# =========================================================
# 9. كلمات الأغاني (Lyrics) 🎤
# =========================================================

@web_bp.route('/api/player/lyrics')
def get_lyrics():
    query = request.args.get('q')
    # هنا ممكن تربط بـ Genius API
    return jsonify({"lyrics": "Lyrics system not configured yet."})
