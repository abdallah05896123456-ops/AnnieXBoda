import os
import sys
import logging
import asyncio
import time
import json
import hashlib
import platform
from datetime import datetime, timedelta
from functools import wraps
from flask import jsonify, session, request, current_app, Response
from dotenv import load_dotenv
from pymongo import MongoClient, errors
from werkzeug.security import generate_password_hash, check_password_hash

# =========================================================
# 1. تهيئة النظام والبيئة (System Bootstrap)
# =========================================================
load_dotenv()

class Config:
    """
    فئة إعدادات النظام المركزية.
    تحتوي على كل الثوابت والمتغيرات.
    """
    # المسارات الأساسية
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DOWNLOADS_DIR = os.path.join(BASE_DIR, "..", "downloads")
    LOG_FILE = os.path.join(BASE_DIR, "..", "AnnieX.log")
    
    # مفاتيح الأمان
    SECRET_KEY = os.getenv("SECRET_KEY", "Titan_Ultimate_Secret_Key_v2_2025")
    SUDO_PASSWORD = os.getenv("SUDO_PASSWORD", "admin")
    API_KEY = os.getenv("API_KEY", "titan_api_key_x1")
    
    # إعدادات السيرفر
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8080))
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    
    # إعدادات قاعدة البيانات
    MONGO_URL = os.getenv("MONGO_URL")
    DB_NAME = "AnnieX_Titan"
    
    # إعدادات الملفات
    ALLOWED_EXTENSIONS = {
        'audio': {'.mp3', '.m4a', '.flac', '.wav', '.ogg', '.opus'},
        'video': {'.mp4', '.mkv', '.webm', '.avi', '.mov'}
    }
    MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB

    @staticmethod
    def init_dirs():
        """إنشاء المجلدات الضرورية عند البدء"""
        if not os.path.exists(Config.DOWNLOADS_DIR):
            os.makedirs(Config.DOWNLOADS_DIR)
            print(f"[INFO] Created Downloads Directory: {Config.DOWNLOADS_DIR}")

# تنفيذ التهيئة
Config.init_dirs()

# =========================================================
# 2. نظام التسجيل المتقدم (Advanced Logger)
# =========================================================
class TitanLogger:
    """
    نظام لوجات مخصص يفصل بين سجلات البوت وسجلات الموقع.
    """
    def __init__(self, name="DashX_Core"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # تنسيق اللوج
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(module)s]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # حفظ في ملف منفصل للموقع
        file_handler = logging.FileHandler('web_dashboard.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        # طباعة في الكونسول
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(stream_handler)

    def info(self, msg, **kwargs):
        self.logger.info(f"{msg} | {kwargs if kwargs else ''}")

    def error(self, msg, error=None):
        err_msg = f"ERROR: {str(error)}" if error else ""
        self.logger.error(f"{msg} {err_msg}")

    def warning(self, msg):
        self.logger.warning(msg)

# إنشاء كائن اللوجر العام
logger = TitanLogger()

def log_activity(action, details=None):
    """دالة مساعدة لتسجيل نشاطات المستخدم"""
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user = session.get('user', 'Guest')
    logger.info(f"ACT: {action}", user=user, ip=ip, details=details)

# =========================================================
# 3. مدير قاعدة البيانات (Database Manager)
# =========================================================
class DatabaseManager:
    """
    غلاف (Wrapper) للتعامل مع MongoDB بأمان.
    """
    def __init__(self):
        self.client = None
        self.db = None
        self.is_connected = False
        self.connect()

    def connect(self):
        if not Config.MONGO_URL:
            logger.warning("MONGO_URL not found in .env")
            return

        try:
            self.client = MongoClient(Config.MONGO_URL, serverSelectionTimeoutMS=3000)
            self.db = self.client[Config.DB_NAME]
            # Test Connection
            self.client.server_info()
            self.is_connected = True
            logger.info("✅ MongoDB Connected Successfully")
        except errors.ServerSelectionTimeoutError:
            logger.error("❌ MongoDB Connection Timeout")
            self.is_connected = False
        except Exception as e:
            logger.error("❌ MongoDB Connection Error", e)
            self.is_connected = False

    def get_collection(self, name):
        if self.is_connected and self.db is not None:
            return self.db[name]
        return None

# إنشاء كائن الداتابيز
db_manager = DatabaseManager()
db = db_manager.db  # للوصول المباشر المتوافق مع الكود القديم

# =========================================================
# 4. الربط مع البوت (Bot Integration Bridge)
# =========================================================
StreamController = None
try:
    from AnnieXMedia.core.call import StreamController as SC
    StreamController = SC
    logger.info("✅ StreamController Imported Successfully")
except ImportError:
    logger.warning("⚠️ StreamController NOT FOUND - Running in Mock Mode")
except Exception as e:
    logger.error("⚠️ StreamController Import Error", e)

def run_async(coro):
    """
    تشغيل دوال Asyncio داخل Flask (Thread-Safe).
    """
    if not coro:
        return None
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        return loop.create_task(coro)
    else:
        return loop.run_until_complete(coro)

# =========================================================
# 5. أدوات معالجة النصوص والأرقام (Formatters)
# =========================================================
class Formatters:
    @staticmethod
    def get_readable_size(size_in_bytes):
        """تحويل البايت إلى صيغة مقروءة"""
        try:
            size_in_bytes = float(size_in_bytes)
            for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
                if size_in_bytes < 1024.0:
                    return f"{size_in_bytes:.2f} {unit}"
                size_in_bytes /= 1024.0
            return f"{size_in_bytes:.2f} EB"
        except (ValueError, TypeError):
            return "0 B"

    @staticmethod
    def format_duration(seconds):
        """تحويل الثواني إلى وقت (HH:MM:SS)"""
        if not seconds or not isinstance(seconds, (int, float)):
            return "00:00"
        try:
            return str(timedelta(seconds=int(seconds)))
        except:
            return "00:00"

    @staticmethod
    def clean_filename(filename):
        """تنظيف اسم الملف من الأحرف الخطرة"""
        from werkzeug.utils import secure_filename
        safe = secure_filename(filename)
        # إضافة timestamp لو الاسم بقى فاضي
        if not safe:
            safe = f"file_{int(time.time())}"
        return safe

# لتسهيل الاستدعاء
get_readable_size = Formatters.get_readable_size
format_duration = Formatters.format_duration

# =========================================================
# 6. الردود القياسية (Standard API Responses)
# =========================================================
class APIResponse:
    @staticmethod
    def success(data=None, message="Operation Successful"):
        res = {"success": True, "message": message}
        if data: res.update(data)
        return jsonify(res), 200

    @staticmethod
    def error(message="Internal Server Error", code=500, details=None):
        res = {"success": False, "error": message}
        if details: res["details"] = str(details)
        return jsonify(res), code

    @staticmethod
    def unauthorized():
        return jsonify({"success": False, "error": "Access Denied"}), 403

# =========================================================
# 7. الحماية والصلاحيات (Security Decorators)
# =========================================================
def sudo_required(f):
    """
    ديكوريتور للتحقق من تسجيل دخول الأدمن.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # السماح في وضع الديباج لو مفيش سيشن (اختياري)
        # if Config.DEBUG: return f(*args, **kwargs)
        
        if not session.get('is_sudo'):
            log_activity("UNAUTHORIZED_ACCESS_ATTEMPT")
            return APIResponse.unauthorized()
        return f(*args, **kwargs)
    return decorated_function

def is_safe_file(filename):
    """التحقق من امتداد الملف"""
    ext = os.path.splitext(filename)[1].lower()
    return (ext in Config.ALLOWED_EXTENSIONS['audio'] or 
            ext in Config.ALLOWED_EXTENSIONS['video'])

# =========================================================
# 8. إدارة الكاش (Cache System)
# =========================================================
class CacheManager:
    """نظام تخزين مؤقت بسيط لتخفيف الحمل"""
    _storage = {}
    _expiry = {}

    @staticmethod
    def set(key, value, ttl=10):
        CacheManager._storage[key] = value
        CacheManager._expiry[key] = time.time() + ttl

    @staticmethod
    def get(key):
        if key in CacheManager._storage:
            if time.time() < CacheManager._expiry.get(key, 0):
                return CacheManager._storage[key]
            else:
                del CacheManager._storage[key]
                del CacheManager._expiry[key]
        return None
