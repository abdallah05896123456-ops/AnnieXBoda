import logging
from flask import Blueprint, render_template

# =========================================================
# 1. تعريف البلوبرينت (The Blueprint)
# =========================================================
# ده الكائن الأساسي اللي كل الملفات التانية مربوطة بيه
web_bp = Blueprint(
    'web', 
    __name__, 
    template_folder='templates', 
    static_folder='static'
)

# إعداد مفتاح سري لتشفير الجلسات (Sessions)
web_bp.secret_key = "DashX_Titan_Ultimate_Secret_Key_2026"

# =========================================================
# 2. تجميع الملفات (The Assembly)
# =========================================================
# ⚠️ مهم جداً: لازم الاستيراد يكون هنا (بعد تعريف web_bp)
# عشان نتجنب مشكلة Circular Import (البيضة ولا الفرخة)

from . import utils   # الأدوات وقاعدة البيانات
from . import player  # المشغل والتحكم
from . import system  # مراقبة السيرفر والترمينال
from . import vault   # الخزنة والرفع

# =========================================================
# 3. الصفحة الرئيسية (Entry Point)
# =========================================================
@web_bp.route('/')
def home():
    """
    الصفحة الرئيسية للموقع.
    """
    return render_template('index.html')

# =========================================================
# 4. معالجة الأخطاء (Error Handlers)
# =========================================================
@web_bp.errorhandler(413)
def request_entity_too_large(error):
    """
    لو حد حاول يرفع ملف أكبر من المسموح بيه
    """
    return {"success": False, "error": "File too large! Max limit exceeded."}, 413

@web_bp.errorhandler(404)
def page_not_found(error):
    return render_template('index.html'), 404

# =========================================================
# 5. إعدادات السيرفر (Server Config Injection)
# =========================================================
@web_bp.record
def record_params(setup_state):
    """
    تعديل إعدادات تطبيق Flask الرئيسي عند تسجيل البلوبرينت.
    هنا بنفتح مساحة الرفع لـ 1 جيجا بايت.
    """
    app = setup_state.app
    # السماح برفع ملفات حتى 1 جيجا (1024 * 1024 * 1024)
    app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024 * 1024
    
    # إيقاف الرسائل المزعجة في الترمينال
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
