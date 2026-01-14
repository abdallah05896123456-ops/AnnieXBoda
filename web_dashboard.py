import os
from flask import Flask, render_template, jsonify
from threading import Thread
import logging

# 1. تحديد مكان فولدر TitanOS بالنسبة للملف ده (هما جنب بعض)
BASE_DIR = os.getcwd() # بياخد مسار الروت الحالي
TITAN_PATH = os.path.join(BASE_DIR, 'TitanOS')

# 2. إعداد فلاسك ليقرأ من المسار الصحيح
app = Flask(__name__, template_folder=TITAN_PATH, static_folder=TITAN_PATH)
app.secret_key = "Titan_Core_Secret"

# إلغاء رسائل اللوج المزعجة
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# --- الصفحات ---
@app.route('/')
def login():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/logs')
def logs():
    return render_template('logs.html')

# --- API وهمي (عشان الزراير متضربش إيرور) ---
@app.route('/api/<action>/<chat_id>', methods=['POST'])
def api_handle(action, chat_id):
    return jsonify({"status": "ok", "msg": f"Command {action} executed"})

# --- دالة التشغيل ---
def run_server():
    try:
        app.run(host="0.0.0.0", port=8080)
    except Exception as e:
        print(f"❌ TitanOS Error: {e}")

def start_titan():
    t = Thread(target=run_server)
    t.daemon = True
    t.start()
    print(f"✅ TitanOS Dashboard Active on Path: {TITAN_PATH}")
