import time
import asyncio
import logging
from datetime import datetime
from flask import jsonify, request, session
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
# إعدادات المشغل المتقدمة
# =========================================================
logger = logging.getLogger("DashX_Player")

# لتخزين حالة التشغيل الوهمية (في حالة عدم وجود اتصال حقيقي)
MOCK_STATE = {
    "status": "playing",
    "volume": 100,
    "speed": 1.0,
    "loop": False,
    "shuffle": False
}

# =========================================================
# 1. واجهة الحالة الحية (Live Status API)
# =========================================================

@web_bp.route('/api/player/status')
def get_player_status():
    """
    جلب الحالة الكاملة للمشغل.
    يدعم تعدد المجموعات (Multi-Chat Support).
    """
    chat_id = request.args.get('chat_id')
    
    # 1. لو مفيش chat_id، رجع حالة عامة للنظام
    if not chat_id:
        return jsonify({
            "state": "idle",
            "message": "Select a chat to view player",
            "active_chats_count": 5  # رقم وهمي للتجربة
        })

    # 2. محاولة جلب البيانات الحقيقية من البوت
    # (هنا بنفترض وجود دوال معينة في StreamController)
    try:
        # real_status = run_async(StreamController.get_active_call(chat_id))
        real_status = None # خليه None حالياً عشان نستخدم الـ Mock
    except:
        real_status = None

    # 3. بيانات المحاكاة (Fallback) لضمان عمل الواجهة
    current_time = time.time()
    track_duration = 240 # 4 دقائق
    position = int(current_time % track_duration)
    
    response = {
        "status": MOCK_STATE["status"],
        "track": {
            "title": "DashX Ultimate Soundtrack",
            "artist": "AnnieX System",
            "album": "Titan V2",
            "cover": "https://telegra.ph/file/8b3e21894d3062325c04b.jpg",
            "duration": track_duration,
            "duration_str": format_duration(track_duration),
            "position": position,
            "position_str": format_duration(position),
            "progress_percent": (position / track_duration) * 100
        },
        "settings": {
            "volume": MOCK_STATE["volume"],
            "speed": MOCK_STATE["speed"],
            "loop": MOCK_STATE["loop"],
            "shuffle": MOCK_STATE["shuffle"]
        },
        "meta": {
            "listeners": 12,
            "chat_id": chat_id,
            "ping": "23ms"
        }
    }
    
    return jsonify(response)

# =========================================================
# 2. واجهة التحكم المركزية (Main Control Hub)
# =========================================================

@web_bp.route('/api/player/control', methods=['POST'])
@sudo_required
def player_control():
    """
    عصب التحكم الرئيسي.
    بيستقبل أي أمر (Pause, Skip, Volume, Seek, etc.)
    """
    if not StreamController:
        return jsonify({"success": False, "error": "Core Disconnected"})

    data = request.json
    action = data.get('action')
    chat_id = data.get('chat_id')
    value = data.get('value') # للقيم المتغيرة زي الصوت والسرعة

    if not chat_id:
        return jsonify({"success": False, "error": "Chat ID Required"})

    log_activity(f"PLAYER_CMD_{action.upper()}", f"Chat: {chat_id}, Val: {value}")

    try:
        # --- أوامر التشغيل الأساسية ---
        if action == 'pause':
            run_async(StreamController.pause_stream(chat_id))
            MOCK_STATE["status"] = "paused"
            
        elif action == 'resume':
            run_async(StreamController.resume_stream(chat_id))
            MOCK_STATE["status"] = "playing"
            
        elif action == 'skip':
            run_async(StreamController.skip_stream(chat_id))
            
        elif action == 'stop':
            # run_async(StreamController.stop_stream(chat_id))
            pass # محتاج دالة stop في البوت

        # --- أوامر التعديل (Advanced) ---
        elif action == 'seek':
            # value هنا بالثواني
            # run_async(StreamController.seek_stream(chat_id, int(value)))
            pass

        elif action == 'volume':
            # value من 0 لـ 200
            # run_async(StreamController.set_volume(chat_id, int(value)))
            MOCK_STATE["volume"] = int(value)

        elif action == 'speed':
            # value: 0.5, 1.0, 1.5, 2.0
            # run_async(StreamController.set_speed(chat_id, float(value)))
            MOCK_STATE["speed"] = float(value)

        # --- أوامر القائمة ---
        elif action == 'loop':
            MOCK_STATE["loop"] = not MOCK_STATE["loop"]
            # منطق تفعيل التكرار في البوت
            
        elif action == 'shuffle':
            MOCK_STATE["shuffle"] = not MOCK_STATE["shuffle"]
            # منطق تفعيل العشوائية

        return jsonify({
            "success": True, 
            "message": f"Executed {action}",
            "new_state": MOCK_STATE
        })

    except Exception as e:
        logger.error(f"Control Error: {e}")
        return jsonify({"success": False, "error": str(e)})

# =========================================================
# 3. إدارة قائمة الانتظار (Queue Management)
# =========================================================

@web_bp.route('/api/player/queue', methods=['GET'])
def get_queue():
    """جلب قائمة الأغاني المنتظرة"""
    chat_id = request.args.get('chat_id')
    # محاكاة قائمة انتظار
    fake_queue = [
        {"id": "vid1", "title": "Alan Walker - Faded", "duration": "3:32", "user": "User1"},
        {"id": "vid2", "title": "Imagine Dragons - Believer", "duration": "3:24", "user": "User2"},
        {"id": "vid3", "title": "Quran - Surah Al-Kahf", "duration": "45:00", "user": "Admin"},
    ]
    return jsonify({"queue": fake_queue})

@web_bp.route('/api/player/queue/action', methods=['POST'])
@sudo_required
def queue_action():
    """تعديل القائمة (حذف، ترتيب)"""
    data = request.json
    action = data.get('action') # 'remove', 'move', 'clear'
    chat_id = data.get('chat_id')
    item_id = data.get('item_id')
    
    # هنا هنحط منطق التعامل مع Queue البوت الحقيقي
    if action == 'clear':
        # run_async(StreamController.clear_queue(chat_id))
        return jsonify({"success": True, "message": "Queue Cleared"})
    
    return jsonify({"success": True})

# =========================================================
# 4. البحث والتشغيل المباشر (Search & Play)
# =========================================================

@web_bp.route('/api/player/play_url', methods=['POST'])
@sudo_required
def play_direct():
    """تشغيل رابط مباشر (Youtube/Link)"""
    data = request.json
    url = data.get('url')
    chat_id = data.get('chat_id')
    
    if not url or not chat_id:
        return jsonify({"success": False, "error": "URL and ChatID required"})

    try:
        # استدعاء دالة التشغيل في البوت
        run_async(StreamController.play_stream(chat_id, url))
        
        # تسجيل في الداتابيز (History)
        if db:
            db.play_history.insert_one({
                "chat_id": chat_id,
                "url": url,
                "played_by": "Web Dashboard",
                "timestamp": datetime.utcnow()
            })

        return jsonify({"success": True, "message": "Request sent to bot"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# =========================================================
# 5. المجموعات النشطة (Active Chats Monitor)
# =========================================================

@web_bp.route('/api/player/active_chats')
def active_chats():
    """جلب كل المجموعات اللي البوت شغال فيها حالياً"""
    # مفروض نجيب ده من Call Container في البايثون
    # محاكاة:
    chats = [
        {"id": -100123456789, "name": "Music Galaxy 🎵", "listeners": 15, "active": True},
        {"id": -100987654321, "name": "Coding Support 💻", "listeners": 3, "active": True},
    ]
    return jsonify({"chats": chats})

# =========================================================
# 6. جلب الكلمات (Lyrics Fetcher)
# =========================================================

@web_bp.route('/api/player/lyrics')
def get_lyrics():
    """جلب كلمات الأغنية الحالية"""
    track_name = request.args.get('track')
    if not track_name: return jsonify({"lyrics": "No track specified"})
    
    # هنا ممكن نربط بـ API خارجي زي Genius
    return jsonify({
        "lyrics": f"[Verse 1]\nLyrics for {track_name} will appear here...\n(Integration pending)"
    })

# =========================================================
# 7. سجل التشغيل (Playback History) - MongoDB
# =========================================================

@web_bp.route('/api/player/history')
def get_history():
    """جلب آخر الأغاني اللي اشتغلت"""
    if not db:
        return jsonify({"history": []})
    
    try:
        history = list(db.play_history.find().sort("timestamp", -1).limit(20))
        # تنظيف البيانات عشان الـ JSON
        for h in history:
            h['_id'] = str(h['_id'])
        return jsonify({"history": history})
    except:
        return jsonify({"history": []})
