# web/security_gate.py
from fastapi import FastAPI, APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import hashlib
import hmac
import jwt
from datetime import datetime, timedelta, timezone
import time
import uuid
from typing import Optional, Dict, List

import config

router = APIRouter(prefix="/auth", tags=["auth"])

# Configurable values with sensible defaults
RATE_LIMIT = int(getattr(config, "RATE_LIMIT", 10))
RATE_PERIOD = int(getattr(config, "RATE_PERIOD", 60))
JWT_ALGORITHM = getattr(config, "JWT_ALGORITHM", "HS256")
JWT_EXP_SECONDS = int(getattr(config, "WEB_SESSION_EXPIRE_SECONDS", 3600))
WEB_SECRET = getattr(config, "WEB_SECRET", None)
WEB_PASSWORD = getattr(config, "WEB_PASSWORD", None)
BOT_TOKEN = getattr(config, "BOT_TOKEN", None)
COOKIE_SECURE = bool(getattr(config, "COOKIE_SECURE", False))
TELEGRAM_AUTH_MAX_AGE = int(getattr(config, "TELEGRAM_AUTH_MAX_AGE_SECONDS", 86400))  # default 24h

if WEB_SECRET is None:
    raise RuntimeError("WEB_SECRET not set in config.py — required for JWT signing")

# In-memory structures (note: ephemeral; replace with Redis for production)
_requests_log: Dict[str, List[float]] = {}         # ip -> [timestamps]
_token_blacklist: Dict[str, float] = {}           # jti -> expiry timestamp (for logout/invalidate)
_seen_telegram_auths: Dict[str, float] = {}       # "tg:<id>:<auth_date>" -> timestamp when seen

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

# ----- Helpers -----
def _get_client_ip(request: Request) -> str:
    # Respect X-Forwarded-For if behind proxy (make sure your proxy sets it)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # may contain multiple IPs
        ip = xff.split(",")[0].strip()
    else:
        ip = request.client.host or "unknown"
    return ip

def _cleanup_request_logs():
    # optional housekeeping for memory
    now = time.time()
    for ip, arr in list(_requests_log.items()):
        _requests_log[ip] = [t for t in arr if now - t < RATE_PERIOD]
        if not _requests_log[ip]:
            del _requests_log[ip]

def _cleanup_blacklist():
    now = time.time()
    for jti, exp_ts in list(_token_blacklist.items()):
        if now >= exp_ts:
            del _token_blacklist[jti]

def _is_token_blacklisted(jti: str) -> bool:
    _cleanup_blacklist()
    return jti in _token_blacklist

def _blacklist_token(jti: str, exp_ts: float):
    _token_blacklist[jti] = exp_ts

def _create_jwt(subject: str, expires_seconds: int = JWT_EXP_SECONDS) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=expires_seconds)
    jti = str(uuid.uuid4())
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": jti,
    }
    token = jwt.encode(payload, WEB_SECRET, algorithm=JWT_ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode()
    return token

def _verify_jwt(token: str) -> dict:
    try:
        payload = jwt.decode(token, WEB_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    # check blacklist
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=401, detail="Malformed token (no jti)")
    if _is_token_blacklisted(jti):
        raise HTTPException(status_code=401, detail="Token revoked")
    return payload

# ----- Rate limiter dependency -----
async def rate_limit_dependency(request: Request):
    ip = _get_client_ip(request)
    now = time.time()
    arr = _requests_log.get(ip, [])
    # clean old
    arr = [t for t in arr if now - t < RATE_PERIOD]
    if len(arr) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many requests")
    arr.append(now)
    _requests_log[ip] = arr
    return True

# ----- Endpoints -----
@router.post("/login", dependencies=[Depends(rate_limit_dependency)])
async def admin_login(data: LoginModel, request: Request):
    if not WEB_PASSWORD:
        raise HTTPException(status_code=500, detail="Server misconfiguration: WEB_PASSWORD not set")
    # Support either plain shared secret or stored hash:
    provided = data.password or ""
    # Hash both sides with sha256 for comparison (we assume config stores plain secret or same hashing method)
    provided_hash = hashlib.sha256(provided.encode()).hexdigest()
    stored_hash = hashlib.sha256(WEB_PASSWORD.encode()).hexdigest()
    if not hmac.compare_digest(provided_hash, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _create_jwt(subject="admin")
    # set cookie
    resp = JSONResponse({"message": "login successful", "token": token})
    resp.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=bool(COOKIE_SECURE),
        samesite="lax",
        max_age=JWT_EXP_SECONDS,
    )
    return resp

@router.post("/telegram", dependencies=[Depends(rate_limit_dependency)])
async def telegram_login(data: TelegramAuthModel, request: Request):
    """
    Verify Telegram login widget data:
    - Build data_check_string from all fields except hash, sorted by key
    - Calculate HMAC-SHA256 using sha256(bot_token) as key
    - Verify equality (constant-time)
    - Check auth_date freshness and replay protection
    """
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Server misconfiguration: BOT_TOKEN not set")
    payload = data.dict()
    incoming_hash = payload.pop("hash", "")
    # Build data_check_string
    kvs = []
    for k in sorted(payload.keys()):
        v = payload[k]
        if v is None:
            v = ""
        kvs.append(f"{k}={v}")
    data_check_string = "\n".join(kvs)
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_hash, incoming_hash):
        raise HTTPException(status_code=401, detail="Telegram auth verification failed")
    # Check auth_date freshness
    now_ts = int(time.time())
    auth_date = int(data.auth_date)
    if now_ts - auth_date > TELEGRAM_AUTH_MAX_AGE:
        raise HTTPException(status_code=401, detail="Telegram auth expired")
    # Replay protection: ensure same (id,auth_date) not reused within short period
    seen_key = f"tg:{data.id}:{auth_date}"
    if seen_key in _seen_telegram_auths:
        # If we've seen it recently, reject (replay)
        raise HTTPException(status_code=401, detail="Telegram auth replay detected")
    # record it for a short while
    _seen_telegram_auths[seen_key] = now_ts + 60  # keep key for 60 seconds
    # housekeeping for seen auths
    for k, v in list(_seen_telegram_auths.items()):
        if now_ts >= v:
            del _seen_telegram_auths[k]
    # Success -> issue JWT
    subject = f"tg:{data.id}"
    token = _create_jwt(subject=subject)
    resp = JSONResponse({"message": "telegram auth successful", "token": token})
    resp.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=bool(COOKIE_SECURE),
        samesite="lax",
        max_age=JWT_EXP_SECONDS,
    )
    return resp

@router.get("/logout", dependencies=[Depends(rate_limit_dependency)])
async def logout(request: Request):
    """
    Logout: read token (cookie or Authorization), add its jti to blacklist until its expiry.
    """
    # get token from cookie or header
    token = None
    if "session" in request.cookies:
        token = request.cookies.get("session")
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
    if not token:
        return JSONResponse({"message": "no active session"}, status_code=200)
    try:
        payload = jwt.decode(token, WEB_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
    except Exception:
        # Malformed token — simply delete cookie
        resp = JSONResponse({"message": "logged out"})
        resp.delete_cookie("session")
        return resp
    jti = payload.get("jti")
    exp_ts = payload.get("exp", int(time.time()))
    if jti:
        # blacklist until original expiry
        _blacklist_token(jti, float(exp_ts))
    resp = JSONResponse({"message": "logged out"})
    resp.delete_cookie("session")
    return resp

# ----- Auth dependency -----
async def require_auth(request: Request):
    # extract token
    token = None
    if "session" in request.cookies:
        token = request.cookies.get("session")
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
    if not token:
        raise HTTPException(status_code=401, detail="Authentication token missing")
    payload = _verify_jwt(token)
    return payload

# ----- Admin-only dependency -----
async def require_admin(payload: dict = Depends(require_auth)):
    sub = payload.get("sub", "")
    if sub != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return payload

# Protected endpoint examples
@router.get("/protected")
async def protected(payload: dict = Depends(require_auth)):
    return {"status": "ok", "user": payload.get("sub")}

@router.get("/me")
async def me(payload: dict = Depends(require_auth)):
    return {"sub": payload.get("sub"), "iat": payload.get("iat"), "exp": payload.get("exp")}

@router.get("/admin-only")
async def admin_only(payload: dict = Depends(require_admin)):
    return {"status": "ok", "admin": payload.get("sub")}

# Export router
def get_router():
    return router

# For quick local testing as standalone app
app = FastAPI(title="AnnieXBoda - Security Gate", version="1.0.0")
app.include_router(router)
