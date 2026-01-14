from flask import Blueprint, render_template, jsonify, request
from AnnieXMedia import app, userbot
from AnnieXMedia.core.call import StreamController
from pytgcalls.exceptions import NoActiveGroupCall
import asyncio

web_bp = Blueprint('web', __name__, template_folder='templates', static_folder='static')

# ==============================
# 1. API: جلب حالة البوت الحالية
# ==============================
@web_bp.route('/api/status')
def get_status():
    """بترجع اسم الأغنية، الوقت، والصورة للواجهة"""
    # هنا محتاجين نجيب البيانات الحقيقية من StreamController
    # (هنفترض وجود متغيرات global أو دالة get_current_playing)
    
    # مثال لبيانات وهمية مؤقتاً لحد ما نربط المتغيرات:
    return jsonify({
        "status": "playing",
        "track": "AnnieX Intro Mix",
        "artist": "DJ Titan",
        "cover": "https://telegra.ph/file/8b3e21894d3062325c04b.jpg",
        "position": 120, # بالثواني
        "duration": 300,
        "listeners": 15,
        "ping": "42ms"
    })

# ==============================
# 2. API: تنفيذ الأوامر (Play, Pause, Skip)
# ==============================
@web_bp.route('/api/control', methods=['POST'])
def control_player():
    data = request.json
    action = data.get('action')
    chat_id = data.get('chat_id') # لو مبعوتش، هنستخدم الجروب الافتراضي

    # استخدام الـ Loop الأساسي للبوت لتنفيذ الأوامر
    loop = asyncio.get_event_loop()

    try:
        if action == 'pause':
            # استدعاء دالة الإيقاف المؤقت من Call Controller
            loop.create_task(StreamController.pause_stream(chat_id))
        
        elif action == 'resume':
            loop.create_task(StreamController.resume_stream(chat_id))
            
        elif action == 'skip':
            loop.create_task(StreamController.skip_stream(chat_id))
            
        elif action == 'volume':
            vol = int(data.get('value', 100))
            loop.create_task(StreamController.change_volume(chat_id, vol))

        return jsonify({"success": True, "message": f"تم تنفيذ {action}"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ==============================
# 3. الصفحة الرئيسية
# ==============================
@web_bp.route('/')
def home():
    return render_template('index.html')
