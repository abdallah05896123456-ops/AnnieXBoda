from flask import Blueprint, render_template

# 1. إعداد البلوبرينت
web_bp = Blueprint(
    'web', 
    __name__, 
    template_folder='templates', 
    static_folder='static',
    url_prefix=''
)

# 2. استيراد الصفحات (بدون utils)
try:
    from . import system
    from . import player
    from . import vault
    print("[INFO] Web Dashboard Routes Loaded ✅")
except ImportError as e:
    print(f"❌ [WEB ERROR] {e}")

# 3. توجيه الأخطاء للصفحة الرئيسية
@web_bp.errorhandler(404)
def not_found(e):
    return render_template('index.html'), 404
