import logging
import traceback
from flask import Blueprint, render_template, jsonify

# =========================================================
# 🔥 نظام كشف الأخطاء وتشغيل الموقع
# =========================================================

try:
    # 1. إعداد البلوبرينت
    web_bp = Blueprint(
        'web', 
        __name__, 
        template_folder='templates', 
        static_folder='static',
        url_prefix=''
    )

    # 2. استيراد الصفحات الداخلية
    # (بنستخدم try داخلية عشان لو ملف واحد باظ، الباقي يكمل)
    try:
        from . import system
        from . import player
        from . import vault
    except ImportError as e:
        print(f"⚠️ [تحذير] بعض الملفات لم يتم استيرادها: {e}")

    # 3. الصفحة الرئيسية (عشان نحل مشكلة Not Found)
    @web_bp.route('/')
    def home():
        return render_template('index.html')

    # 4. صفحة الحالة (Status Check)
    # دي ميزة زيادة عشان تتأكد إن الموقع شغال حتى لو الصفحة الرئيسية فيها مشكلة
    @web_bp.route('/status')
    def status():
        return jsonify({
            "status": "online", 
            "message": "Titan OS is Running 💎", 
            "heartbeat": "Alive 🫶"
        }), 200

    # 5. معالج الأخطاء
    @web_bp.errorhandler(404)
    def not_found(e):
        return render_template('index.html'), 404

    # =========================================================
    # ✅ رسالة النجاح (لو وصل هنا يبقى مفيش أخطاء قاتلة)
    # =========================================================
    print("\n")
    print("==================================================")
    print("✅ الموقع اشتغل وزي الفل 🫶 (Dashboard Loaded)")
    print("💎 TITAN OS WEB: ONLINE")
    print("==================================================")
    print("\n")

except Exception as e:
    # ❌ رسالة الفشل (لو حصلت مصيبة)
    print("\n")
    print("==================================================")
    print("❌ خطأ قاتل في تشغيل الموقع (CRITICAL WEB ERROR)")
    print(f"Details: {e}")
    print("==================================================")
    traceback.print_exc()
    print("\n")
