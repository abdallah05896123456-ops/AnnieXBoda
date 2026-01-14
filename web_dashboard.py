import os
import logging
from flask import Flask, render_template, jsonify
from threading import Thread

# 1. تحديد مكان فولدر TitanOS (بما إنهم جيران في الروت)
CURRENT_DIR = os.getcwd()
TITAN_DIR = os.path.join(CURRENT_DIR, 'TitanOS')

# 2. إعداد فلاسك
app = Flask(__name__, template_folder=TITAN_DIR, static_folder=TITAN_DIR)
app.secret_key = "Titan_Secret_Key_2025"

# 3. إخفاء رسائل اللوج
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# --- الصفحات ---
@app.route('/')
def home():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/logs')
def logs():
    return render_template('logs.html')

@app.route('/api/<action>/<chat_id>', methods=['POST'])
def api(action, chat_id):
    return jsonify({"status": "Success", "msg": f"Action {action} done"})

# --- التشغيل ---
def run():
    # تشغيل على بورت 8080 عشان الدوكر
    app.run(host="0.0.0.0", port=8080, use_reloader=False)

def start_titan():
    t = Thread(target=run)
    t.daemon = True
    t.start()
