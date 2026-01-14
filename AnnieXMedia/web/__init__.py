import logging
from flask import Flask, Blueprint, render_template, jsonify, request
from werkzeug.exceptions import HTTPException

# =========================================================
# 1. إعداد البلوبرينت (Blueprint Setup)
# =========================================================
# هذا الكائن هو الوعاء الذي يحتوي كل الراوتات السابقة
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
# يجب استيراد الملفات بعد تعريف web_bp

try:
    from . import utils
    from . import system
    from . import vault
    from . import player
    print("[INFO] Web Modules Loaded Successfully")
except ImportError as e:
