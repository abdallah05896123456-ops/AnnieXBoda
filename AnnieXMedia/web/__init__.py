import logging
from flask import Flask, Blueprint, render_template, jsonify, request
from werkzeug.exceptions import HTTPException

# =========================================================
# 1. إعداد البلوبرينت (Blueprint Setup)
# =========================================================
web_bp = Blueprint(
    'web', 
    __name__, 
    template_folder='templates', 
    static_folder='static',
    url_prefix=''
)

# =========================================================
# 2. استيراد المكونات (Module Loading)
# =========================================================
# الترتيب مهم جداً هنا لتجنب Circular Import

try:
    # النقطة (.) تعني الاستيراد من نفس المجلد الحالي
    from . import utils
    from . import system
    from . import vault
    from . import player
    print("[INFO] Web Modules Loaded Successfully ✅")

except ImportError as e:
    # هنا كان الخطأ: لازم نكتب حاجة تحت الـ except
    print(f"❌ [WEB CRITICAL ERROR] Failed to load dashboard modules: {e}")
    # ممكن نضيف traceback عشان نعرف تفاصيل أكتر لو الخطأ صعب
    import traceback
    traceback.print_exc()

# =========================================================
# 3. معالج الأخطاء (Error Handlers) - اختياري
# =========================================================
@web_bp.errorhandler(404)
def not_found(e):
    return render_template('index.html'), 200  # بنرجعه للصفحة الرئيسية بدل صفحة الخطأ
