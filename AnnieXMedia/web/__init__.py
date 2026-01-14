import time
import logging
import traceback
from flask import Blueprint, render_template, jsonify, g, request

# =========================================================
# 1. إعداد البلوبرينت (The Core)
# =========================================================
web_bp = Blueprint(
    'web', 
    __name__, 
    template_folder='templates', # مكان ملفات HTML
    static_folder='static',      # مكان CSS و JS (مهم جداً!)
    url_prefix=''                # عشان يفتح على الدومين الرئيسي
)

# =========================================================
# 2. مراقب الأداء (Performance Monitor)
# لو أي صفحة أخدت أكتر من 5 ثواني، هيطبع إنذار في اللوجز
# =========================================================
@web_bp.before_request
def start_timer():
    """تسجيل وقت بداية الطلب"""
    g.start = time.time()

@web_bp.after_request
def log_slow_request(response):
    """حساب الوقت المستغرق قبل الرد"""
    if hasattr(g, 'start'):
        duration = time.time() - g.start
        
        # إذا تجاوز الوقت 5 ثواني
        if duration > 5:
            print(f"\n❌ [TIMEOUT WARNING] Page: {request.path} took {duration:.2f}s")
            print(f"⚠️  Possible causes: Slow internet, heavy loop, or missing file.\n")
            
    return response

# =========================================================
# 3. ربط الموديلات (Linking Modules)
# هنا بنربط كل ملفات البايثون ببعض عشان الموقع يشوف كل الأكواد
# =========================================================
print("[INFO] Initializing Web Dashboard...")

try:
    # استدعاء الملفات الفرعية (يجب أن يكون بعد تعريف web_bp)
    from . import utils    # الأدوات المساعدة
    from . import system   # إحصائيات الرامات والمعالج
    from . import player   # التحكم في الموسيقى
    from . import vault    # إدارة الملفات
    
    print("[INFO] ✅ All Modules Linked Successfully (Utils, System, Player, Vault)")

except ImportError as e:
    # لو فيه ملف ناقص أو فيه خطأ، هيطبعلك هو مين بالظبط
    print(f"\n❌ [CRITICAL ERROR] Failed to link modules: {e}")
    print("👉 Please check that 'system.py', 'player.py', and 'vault.py' exist in 'AnnieXMedia/web/' folder.\n")
    traceback.print_exc()

# =========================================================
# 4. الراوتات الأساسية (Basic Routes)
# =========================================================

@web_bp.route('/')
def home():
    """الصفحة الرئيسية"""
    return render_template('index.html')

@web_bp.route('/status')
def status():
    """فحص حالة السيرفر"""
    return jsonify({
        "status": "online", 
        "system": "Titan OS v3.0", 
        "modules_loaded": True
    }), 200

# =========================================================
# 5. معالجة الأخطاء (Error Handlers)
# =========================================================
@web_bp.errorhandler(404)
def not_found(e):
    # لو اليوزر طلب صفحة مش موجودة، نرجعه للرئيسية بدل ما يشوف Error
    return render_template('index.html'), 404

@web_bp.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal Server Error", "details": str(e)}), 500
