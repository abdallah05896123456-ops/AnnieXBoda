# Authored By Certified Coders © 2025
from flask import Flask
from config import WEB_SECRET
import logging

# إخفاء رسائل Flask المزعجة في التيرمنال
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

def create_app():
    # إعداد تطبيق فلاسك
    app_web = Flask(__name__)
    app_web.secret_key = WEB_SECRET
    
    # استيراد ملف الروابط (هنعمله الخطوة الجاية)
    from AnnieXMedia.web.routes import web_bp
    app_web.register_blueprint(web_bp)
    
    return app_web
