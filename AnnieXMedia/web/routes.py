from flask import Blueprint, render_template, jsonify, request
import os

# تعريف الـ Blueprint (لازم يكون اسمه web_bp عشان main.py يشوفه)
web_bp = Blueprint('web', __name__, template_folder='templates', static_folder='static')

# ==============================
# 1. تشغيل واجهة المستخدم
# ==============================
@web_bp.route('/')
def dashboard_home():
    """تحميل واجهة الـ Dashboard"""
    return render_template('index.html')

# ==============================
# 2. بوابة التحكم (API Gateway)
# ==============================
@web_bp.route('/api/bot/stats', methods=['GET'])
def get_stats():
    """إرسال إحصائيات البوت للموقع"""
    # هنا هنربط بالبيانات الحقيقية لاحقاً
    return jsonify({
        "cpu": "15%",
        "ram": "200MB",
        "ping": "30ms",
        "active_chats": 5
    })

@web_bp.route('/api/player/action', methods=['POST'])
def player_action():
    """استقبال أوامر التشغيل من الموقع"""
    data = request.json
    print(f"⚡ Web Action: {data}")
    return jsonify({"status": "success", "executed": data.get('command')})
