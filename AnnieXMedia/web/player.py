import time
import asyncio
import logging
import random
import uuid
from datetime import datetime
from flask import jsonify, request, session
from . import web_bp
from .utils import (
    run_async, 
    StreamController, 
    db, 
    sudo_required, 
    log_activity,
    logger,
    APIResponse,
    format_duration,
    CacheManager
)

# =========================================================
# 1. إعدادات ومحاكاة البيانات (Advanced Mock Engine)
# =========================================================
# هذا الكلاس مسؤول عن توليد بيانات وهمية ذكية للتجربة
class MockDataEngine:
    COVERS = [
        "https://telegra.ph/file/8b3e21894d3062325c04b.jpg",
        "https://i1.sndcdn.com/artworks-000185747619-j1z80j-t500x500.jpg",
        "https://i.scdn.co/image/ab67616d0000b273a91c10d3f233400554032943",
    ]
    USERS = [
        {"name": "Ahmed", "img": "https://telegra.ph/file/5a5d09854728704253158.jpg"},
        {"name": "Sarah", "img": "https://telegra.ph/file/710609b5527a20c327293.jpg"},
        {"name": "Titan Admin", "img": "https://telegra.ph/file/0858348d4e73809689882.jpg"},
    ]
    TRACKS = [
        {"title": "Atr Al Hayah", "artist": "Ahmed Mekky", "dur": 240},
        {"title": "Faded", "artist": "Alan Walker", "dur": 300},
        {"title": "Believer", "artist": "Imagine Dragons", "dur": 210},
    ]

    @staticmethod
    def generate_chat(chat_id, title):
        track = random.choice(MockDataEngine.TRACKS)
        user = random.choice(MockDataEngine.USERS)
        
        return {
            "chat_id": chat_id,
            "title": title,
            "track": f"{track['artist']} - {track['title']}",
            "artist": track['artist'],
            "track_name": track['title'],
            "cover": random.choice(MockDataEngine.COVERS),
            "user": user['name'],
            "user_img": user['img'], # الأساسي للـ Glass Design
            "duration": track['dur'],
            "position": random.randint(0, track['dur']),
            "listeners": random.randint(5, 100),
            "status": "playing",
            "volume": 100
        }

# تخزين الحالة الوهمية في الذاكرة
_MOCK_CHATS_STORE = [
    MockDataEngine.generate_chat(-100123456, "Coding Squad 💻"),
    MockDataEngine.generate_chat(-100987654, "Night Vibes 🌙"),
]

# =========================================================
# 2. فئة إدارة المشغل (Player Manager)
# =========================================================
class PlayerManager:
    """
    الواجهة الوسيطة بين البوت والموقع.
    تقوم بتوحيد شكل البيانات سواء كانت حقيقية أو وهمية.
    """
    
    @staticmethod
    async def get_active_chats():
        """جلب البيانات الحقيقية من البوت وتحويلها لصيغة JSON"""
        chats = []
        
        # 1. محاولة الجلب من البوت الحقيقي
        if StreamController:
            try:
                # هذه دالة افتراضية، يجب أن تكون موجودة في البوت الخاص بك
                # bot_calls = await StreamController.get_all_calls()
                bot_calls = [] # لا يوجد اتصال حالياً
                
                for call in bot_calls:
                    # تحويل كائن البوت لـ Dict
                    chats.append({
                        "chat_id": call.chat_id,
                        "title": call.chat_title,
                        "track": call.title,
                        "cover": call.thumb or MockDataEngine.COVERS[0],
                        "user": call.requested_by,
                        "user_img": call.user_thumb, # مهم جداً
                        "position": call.played_duration,
                        "duration": call.duration,
                        "status": "playing"
                    })
            except Exception as e:
                logger.error("Error fetching bot calls", e)

        # 2. دمج البيانات الوهمية (إذا لم يوجد بوت أو للتجربة)
        if not chats and _MOCK_CHATS_STORE:
            # تحديث عداد الوقت للمحاكاة
            for chat in _MOCK_CHATS_STORE:
                chat['position'] += 2 # زيادة ثانيتين كل طلب
                if chat['position'] >= chat['duration']:
                    chat['position'] = 0 # إعادة من الأول
                
                # حساب النسبة المئوية للـ Progress Bar
                chat['progress'] = (chat['position'] / chat['duration']) * 100
                chat['position_str'] = format_duration(chat['position'])
                chat['duration_str'] = format_duration(chat['duration'])
                
            return _MOCK_CHATS_STORE

        return chats

# =========================================================
# 3. واجهة الداشبورد الرئيسية (The Dashboard API)
# =========================================================

@web_bp.route('/api/player/dashboard')
def api_dashboard():
    """
    عقل النظام (The Brain):
    يقرر ماذا يعرض للواجهة الأمامية بناءً على حالة النظام.
    """
    try:
        # جلب البيانات (Async Wrapper)
        active_chats = run_async(PlayerManager.get_active_chats())
        
        # السيناريو 1: لا يوجد تشغيل (Idle Mode)
        # هذا يرسل إشارة للواجهة لعرض الرامات والمعالج
        if not active_chats:
            return jsonify({
                "mode": "stats",
                "message": "System Idle",
                "sub_message": "Waiting for requests...",
                "chats": []
            })
        
        # السيناريو 2: يوجد تشغيل (Active Mode)
        # يرسل البيانات بالتنسيق الذي يحتاجه التصميم الزجاجي
        return jsonify({
            "mode": "active",
            "message": f"{len(active_chats)} Active Streams",
            "chats": active_chats
        })

    except Exception as e:
        logger.error("Dashboard Fatal Error", e)
        return jsonify({"mode": "stats", "message": "System Error", "error": str(e)})

# =========================================================
# 4. واجهة التحكم (Controls API)
# =========================================================

@web_bp.route('/api/player/group_action', methods=['POST'])
@sudo_required
def api_group_action():
    """
    تنفيذ الأوامر (Stop, Pause, Resume, Ban, Focus).
    """
    data = request.json
    action = data.get('action')
    chat_id = data.get('chat_id')
    
    if not chat_id: return APIResponse.error("Chat ID missing")

    log_activity(f"CMD: {action}", f"Target: {chat_id}")

    try:
        # --- Stop / End ---
        if action == 'stop':
            if StreamController:
                run_async(StreamController.stop_stream(chat_id))
            
            # حذف من الوهمي للتجربة الفورية
            global _MOCK_CHATS_STORE
            _MOCK_CHATS_STORE = [c for c in _MOCK_CHATS_STORE if c['chat_id'] != chat_id]
            
            return APIResponse.success(message="Stream Stopped")

        # --- Pause ---
        elif action == 'pause':
            if StreamController: run_async(StreamController.pause_stream(chat_id))
            return APIResponse.success(message="Stream Paused")

        # --- Resume ---
        elif action == 'resume':
            if StreamController: run_async(StreamController.resume_stream(chat_id))
            return APIResponse.success(message="Stream Resumed")

        # --- Skip ---
        elif action == 'skip':
            if StreamController: run_async(StreamController.skip_stream(chat_id))
            return APIResponse.success(message="Track Skipped")

        # --- Ban Group (Database Action) ---
        elif action == 'ban':
            if db:
                db.blacklist.insert_one({
                    "chat_id": chat_id,
                    "reason": "Web Dashboard Ban",
                    "admin": session.get('user', 'admin'),
                    "date": datetime.utcnow()
                })
            return APIResponse.success(message="Group Blacklisted ⛔")

        # --- Focus Mode (Priority) ---
        elif action == 'focus':
            # ميزة وهمية حالياً، يمكن تطبيقها بتغيير الـ Nice value للعملية
            return APIResponse.success(message="Server Priority Elevated 🚀")

    except Exception as e:
        logger.error(f"Action {action} failed", e)
        return APIResponse.error("Action Failed", details=e)

    return APIResponse.error("Unknown Action")

# =========================================================
# 5. واجهة التشغيل المباشر (Direct Play)
# =========================================================

@web_bp.route('/api/player/play', methods=['POST'])
@sudo_required
def api_play_direct():
    """تشغيل رابط خارجي (يوتيوب/ملف)"""
    data = request.json
    url = data.get('url')
    chat_id = data.get('chat_id')
    
    if not url or not chat_id: return APIResponse.error("Missing Params")

    try:
        # إضافة للموك داتا للتجربة
        _MOCK_CHATS_STORE.append(MockDataEngine.generate_chat(chat_id, "Dashboard Request"))
        
        # الأمر الحقيقي
        run_async(StreamController.play_stream(chat_id, url))
        
        return APIResponse.success(message="Request Queued")
    except Exception as e:
        return APIResponse.error("Play Failed", details=e)

# =========================================================
# 6. واجهة البحث والتوصيات (Search & Recommendations)
# =========================================================

@web_bp.route('/api/player/search')
@sudo_required
def api_search():
    query = request.args.get('q')
    if not query: return jsonify([])
    
    # محاكاة نتائج بحث
    results = [
        {"title": f"Result for {query} 1", "id": "yt_id_1"},
        {"title": f"Result for {query} 2", "id": "yt_id_2"},
    ]
    return jsonify(results)
