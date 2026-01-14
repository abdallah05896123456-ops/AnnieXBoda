# security_gate.py
from fastapi import FastAPI, APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import hashlib
import hmac
import jwt
from datetime import datetime, timedelta
import time
from typing import Optional, Dict, List
import config

# إعداد الـ router (يمكن تضمينه في تطبيق FastAPI أكبر)
router = APIRouter(prefix="/auth", tags=["auth"])

# إعدادات جلسات وRate limiting (بسيطة داخل الذاكرة)
RATE_LIMIT = int(getattr(config, "RATE_LIMIT", 10))        # عدد الطلبات
RATE_PERIOD = int(getattr(config, "RATE_PERIOD", 60))     # خلال (ثواني)
_requests_log: Dict[str, List[float]] = {}                # ip -> [timestamps]

JWT_ALGORITHM = "HS256"
JWT_EXP_SECONDS = int(getattr(config, "WEB_SESSION_EXPIRE_SECONDS", 3600))  # مدة الجلسة (افتراضي ساعة)

# ----- Models -----
class LoginModel(BaseModel):
    password: str

class TelegramAuthModel(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    auth_date: int
    hash: str

# ----- Rate limiter middleware / dependency -----
async def rate_limit_dependency(request: Request):
    """
    يمكن استدعاؤها كـ dependency على endpoints لحماية ضد طلبات زائدة.
    """
    ip = request.client.host or "unknown"
    now = time.time()
    arr = _requests_log.get(ip, [])
    # نظف السجلات القديمة
    arr = [t for t in arr if now - t < RATE_PERIOD]
    if len(arr) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many requests")
    arr.append(now)
    _requests_log[ip] = arr
    return True

# ----- Helper: JWT -----
def create_jwt(subject: str, expires_seconds: int = JWT_EXP_SECONDS) -> str:
    payload = {
        "sub": subject,
        "exp": datetime.utcnow().timestamp() + expires_seconds,
        "iat": datetime.utcnow().timestamp(),
    }
    token = jwt.encode(payload, config.WEB_SECRET, algorithm=JWT_ALGORITHM)
    # PyJWT >=2 returns str, else bytes
    if isinstance(token, bytes):
        token = token.decode()
    return token

def verify_jwt(token: str) -> dict:
    try:
        payload = jwt.decode(token, config.WEB_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ----- Endpoints -----
@router.post("/login", dependencies=[Depends(rate_limit_dependency)])
async def admin_login(data: LoginModel, request: Request):
    """
    تسجيل دخول الادمن. يقارن SHA-256 لكلمة السر (آمنة كافياً هنا).
    عند النجاح يرجع JWT (يمكن تخزينه في كوكي httpOnly أو استعماله في Authorization header).
    """
    # مقارنة مشفرة بطريقة مقاومة للتوقيت
    provided_hash = hashlib.sha256(data.password.encode()).hexdigest()
    stored_hash = hashlib.sha256(config.WEB_PASSWORD.encode()).hexdigest()
    if not hmac.compare_digest(provided_hash, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_jwt(subject="admin")
    resp = JSONResponse({"message": "login successful", "token": token})
    # ضع الtoken في كوكي httpOnly
    resp.set_cookie("session", token, httponly=True, secure=False, samesite="lax", max_age=JWT_EXP_SECONDS)
    return resp

@router.post("/telegram", dependencies=[Depends(rate_limit_dependency)])
async def telegram_login(data: TelegramAuthModel, request: Request):
    """
    تحقق من بيانات تسجيل تيليجرام (Telegram Login Widget).
    بناء data_check_string ثم HMAC-SHA256 باستخدام SHA256(bot_token) كـ key.
    """
    # جهز بيانات التحقق (جميع الحقول عدا hash، مرتبة أبجدياً)
    incoming = data.dict()
    incoming_hash = incoming.pop("hash")
    # تحضير data_check_string
    kvs = []
    for k in sorted(incoming.keys()):
        v = incoming[k]
        if v is None:
            v = ""
        kvs.append(f"{k}={v}")
    data_check_string = "\n".join(kvs)
    secret_key = hashlib.sha256((config.BOT_TOKEN or "").encode()).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_hash, incoming_hash):
        raise HTTPException(status_code=401, detail="Telegram auth verification failed")
    # التحقق ناجح -> اصدر توكن JWT للمستخدم
    subject = f"tg:{data.id}"
    token = create_jwt(subject=subject)
    resp = JSONResponse({"message": "telegram auth successful", "token": token})
    resp.set_cookie("session", token, httponly=True, secure=False, samesite="lax", max_age=JWT_EXP_SECONDS)
    return resp

@router.get("/logout")
async def logout(request: Request):
    resp = JSONResponse({"message": "logged out"})
    resp.delete_cookie("session")
    return resp

# ----- Dependency للتحقق من الجلسة -----
async def require_auth(request: Request):
    """
    يتحقق من وجود JWT في الكوكي أو Authorization header.
    يعيد الـ payload عند النجاح.
    """
    token = None
    # 1. كوكي باسم session
    if "session" in request.cookies:
        token = request.cookies.get("session")
    # 2. header Authorization: Bearer <token>
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
    if not token:
        raise HTTPException(status_code=401, detail="Authentication token missing")
    payload = verify_jwt(token)
    return payload

# Endpoint اختباري محمي
@router.get("/protected")
async def protected(payload: dict = Depends(require_auth)):
    return {"status": "ok", "user": payload.get("sub")}

# ----- Export كـ FastAPI app (اختياري) -----
def get_router():
    return router

# إذا عايز تشغله مستقلاً:
app = FastAPI(title="AnnieXBoda - Security Gate", version="1.0.0")
app.include_router(router)
