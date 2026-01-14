from quart import Quart, render_template, jsonify, request
import asyncio
from threading import Thread

# 1. تعريف التطبيق وتحديد مكان ملفات التصميم
# template_folder='templates' -> عشان يقرأ الـ HTML
# static_folder='static' -> عشان يقرأ الـ CSS والـ JS اللي هنعملهم بعدين
app = Quart(__name__, template_folder='templates', static_folder='static')

# ==============================
# 2. الصفحة الرئيسية
# ==============================
@app.route('/')
async def home():
    """أول ما تفتح الموقع، هيعرض ملف index.html"""
    return await render_template('index.html')

# ==============================
# 3. نقطة فحص النظام (API)
# ==============================
@app.route('/api/status')
async def system_status():
    """عشان نتأكد إن الموقع واصل بالبوت"""
    return jsonify({
        "status": "online",
        "bot_name": "AnnieX-Titan",
        "theme": "Glassy-iOS"
    })

# ==============================
# 4. دالة التشغيل (Run)
# ==============================
def run_flask_app():
    # تشغيل السيرفر على بورت 8080 (أو أي بورت تحبه)
    # use_reloader=False مهم عشان ميعملش مشاكل مع البوت
    app.run(host="0.0.0.0", port=8080, use_reloader=False)

def start_web():
    """الدالة دي اللي هنستدعيها في ملف البوت الرئيسي"""
    t = Thread(target=run_flask_app)
    t.daemon = True
    t.start()
