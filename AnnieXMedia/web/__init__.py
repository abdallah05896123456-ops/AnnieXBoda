import asyncio
from flask import Blueprint, render_template, jsonify, request
# استيراد كائنات البوت (تأكد من المسارات حسب مشروعك)
from AnnieXMedia import app as bot_app
from AnnieXMedia.core.call import StreamController

# تعريف البلوبرينت
web_bp = Blueprint('web', __name__, template_folder='templates', static_folder='static')

# ==============================
# 1. الصفحة الرئيسية
# ==============================
@web_bp.route('/')
def home():
    """تحميل واجهة الـ Dashboard"""
    return render_template('index.html')

# ==============================
# 2. API: حالة المشغل (Status)
# ==============================
@web_bp.route('/api/status')
def get_status():
    """إرسال بيانات الأغنية الحالية للواجهة"""
    # حالياً بنبعت بيانات افتراضية لحد ما نربط متغيرات البوت المباشرة
    # في الخطوات الجاية هنخلي القيم دي تيجي من active_calls
    return jsonify({
        "status": "playing",
        "track": "AnnieX System Active", 
        "artist": "Waiting for commands...",
        "cover": "https://telegra.ph/file/8b3e21894d3062325c04b.jpg",
        "position": 0,
        "duration": 100,
        "listeners": 0,
        "ping": "Online"
    })

# ==============================
# 3. API: التحكم (Controls)
# ==============================
@web_bp.route('/api/control', methods=['POST'])
def control_player():
    """استقبال الأوامر من أزرار الموقع"""
    try:
        data = request.json
        action = data.get('action')
        chat_id = data.get('chat_id') 

        # لو مفيش شات ايدي مبعوت، ممكن نستخدم واحد افتراضي أو نرجع خطأ
        # حالياً للتجربة:
        if not chat_id:
            return jsonify({"success": False, "error": "Chat ID Missing"})

        # الحصول على الـ Event Loop الخاص بالبوت
        loop = asyncio.get_event_loop()

        # تنفيذ الأمر بناءً على الزر المضغوط
        if action == 'pause':
            # تشغيل دالة البوت في الخلفية
            loop.create_task(StreamController.pause_stream(chat_id))
            
        elif action == 'resume':
            loop.create_task(StreamController.resume_stream(chat_id))
            
        elif action == 'skip':
            loop.create_task(StreamController.skip_stream(chat_id))

        print(f"✅ Web Control: {action} -> {chat_id}")
        return jsonify({"success": True, "action": action})

    except Exception as e:
        print(f"❌ Web Error: {e}")
        return jsonify({"success": False, "error": str(e)})
