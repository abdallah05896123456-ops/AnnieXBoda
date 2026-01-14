# web/security_gate.py
import hashlib
import hmac
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from argon2 import PasswordHasher, exceptions as argon2_exceptions
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import jwt

import config

router = APIRouter(prefix="/auth", tags=["auth"])

ph = PasswordHasher(time_cost=2, memory_cost=102400, parallelism=8, hash_len=32)

JWT_ALG = getattr(config, "JWT_ALGORITHM", "HS256")
JWT_EXP_SECONDS = int(getattr(config, "WEB_SESSION_EXPIRE_SECONDS", 3600))
WEB_SECRET = getattr(config, "WEB_SECRET", None)
if not WEB_SECRET:
    raise RuntimeError("WEB_SECRET required in config.py")

# Rate-limiting structures and IP ban
_RATE_LIMIT = int(getattr(config, "RATE_LIMIT", 30))
_RATE_PERIOD = int(getattr(config, "RATE_PERIOD", 60))
_ip_log: Dict[str, List[float]] = {}
_ip_ban: Dict[str, float] = {}  # ip -> banned_until timestamp

# Ghost mode token allowlist (owner-only secrets)
_OWNER_HWID = getattr(config, "OWNER_HWID", None)  # precomputed string
_GHOST_TOKENS: List[str] = getattr(config, "GHOST_TOKENS", [])  # pre-shared tokens for owner ghost mode

# HWID generation: use machine-id + mac addresses as baseline
def compute_local_hwid() -> str:
    parts = []
    try:
        if os.path.exists("/etc/machine-id"):
            with open("/etc/machine-id", "r") as f:
                parts.append(f.read().strip())
    except Exception:
        pass
    # add mac addresses
    try:
        import netifaces  # optional; if not present fallback to uuid.getnode
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface).get(netifaces.AF_LINK, [])
            for a in addrs:
                mac = a.get("addr")
                if mac:
                    parts.append(mac)
    except Exception:
        parts.append(str(uuid.getnode()))
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()

# JWT helpers
def create_jwt(sub: str, extra: Optional[dict] = None, exp_seconds: int = JWT_EXP_SECONDS) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "iat": int(now.timestamp()), "exp": int((now + timedelta(seconds=exp_seconds)).timestamp()), "jti": str(uuid.uuid4())}
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, WEB_SECRET, algorithm=JWT_ALG)
    if isinstance(token, bytes):
        token = token.decode()
    return token

def verify_jwt(token: str) -> dict:
    try:
        payload = jwt.decode(token, WEB_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

# Rate limiter dependency
def _client_ip(request: Request):
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host or "unknown"

def rate_limit_check(request: Request):
    ip = _client_ip(request)
    now = time.time()
    # check ban
    if ip in _ip_ban and _ip_ban[ip] > now:
        raise HTTPException(status_code=403, detail="IP temporarily banned")
    arr = _ip_log.get(ip, [])
    arr = [t for t in arr if now - t < _RATE_PERIOD]
    if len(arr) >= _RATE_LIMIT:
        # escalate ban
        _ip_ban[ip] = now + 60 * 15  # 15 minutes
        _ip_log[ip] = []
        raise HTTPException(status_code=429, detail="Rate limit exceeded; IP temporarily banned")
    arr.append(now)
    _ip_log[ip] = arr

# Admin login using Argon2 hashed password stored in config.WEB_PASSWORD_HASH or plain secret
@router.post("/login")
async def admin_login(request: Request, password: dict):
    rate_limit_check(request)
    pwd = password.get("password", "")
    # support both hashed and plain (if config has plain, we hash and compare)
    stored_hash = getattr(config, "WEB_PASSWORD_HASH", None)
    plain_secret = getattr(config, "WEB_PASSWORD", None)
    if stored_hash:
        try:
            ph.verify(stored_hash, pwd)
            token = create_jwt("admin")
            resp = JSONResponse({"message": "ok", "token": token})
            resp.set_cookie("session", token, httponly=True, secure=bool(getattr(config, "COOKIE_SECURE", False)))
            return resp
        except argon2_exceptions.VerifyMismatchError:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    elif plain_secret:
        # constant-time compare
        if hmac.compare_digest(hashlib.sha256(pwd.encode()).hexdigest(), hashlib.sha256(plain_secret.encode()).hexdigest()):
            token = create_jwt("admin")
            resp = JSONResponse({"message": "ok", "token": token})
            resp.set_cookie("session", token, httponly=True, secure=bool(getattr(config, "COOKIE_SECURE", False)))
            return resp
        raise HTTPException(status_code=401, detail="Invalid credentials")
    else:
        raise HTTPException(status_code=500, detail="No password configured")

# Telegram widget verification (same approach as earlier)
@router.post("/telegram")
async def telegram_auth(data: dict, request: Request):
    rate_limit_check(request)
    bot_token = getattr(config, "BOT_TOKEN", None)
    if not bot_token:
        raise HTTPException(status_code=500, detail="Bot token not configured")
    payload = data.copy()
    incoming_hash = payload.pop("hash", "")
    kvs = []
    for k in sorted(payload.keys()):
        v = payload[k]
        if v is None:
            v = ""
        kvs.append(f"{k}={v}")
    data_check_string = "\n".join(kvs)
    secret = hashlib.sha256(bot_token.encode()).digest()
    calc = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, incoming_hash):
        raise HTTPException(status_code=401, detail="Telegram verification failed")
    # check auth_date freshness
    auth_date = int(payload.get("auth_date", 0))
    if time.time() - auth_date > int(getattr(config, "TELEGRAM_AUTH_MAX_AGE", 86400)):
        raise HTTPException(status_code=401, detail="Telegram auth expired")
    sub = f"tg:{payload.get('id')}"
    token = create_jwt(sub)
    resp = JSONResponse({"message": "ok", "token": token})
    resp.set_cookie("session", token, httponly=True, secure=bool(getattr(config, "COOKIE_SECURE", False)))
    return resp

# HWID lock endpoint - owner can lock this dashboard to a HWID
@router.post("/hwid/lock")
async def hwid_lock(request: Request, body: dict):
    rate_limit_check(request)
    secret = body.get("secret")
    # only allow admin/jwt
    auth = request.cookies.get("session") or request.headers.get("Authorization", "").split(" ")[-1]
    if not auth:
        raise HTTPException(status_code=401)
    payload = verify_jwt(auth)
    if payload.get("sub") != "admin":
        raise HTTPException(status_code=403)
    hwid = compute_local_hwid()
    # store in config file? we store in config by writing to a local .hwid file
    with open(".titan_hwid", "w") as f:
        f.write(hwid)
    return {"status": "locked", "hwid": hwid}

@router.get("/hwid/check")
async def hwid_check():
    local = compute_local_hwid()
    locked = None
    if os.path.exists(".titan_hwid"):
        with open(".titan_hwid", "r") as f:
            locked = f.read().strip()
    return {"local_hwid": local, "locked_to": locked, "owner_allowed": (_OWNER_HWID == local)}

# Ghost mode: owner may provide pre-shared token (GHOST_TOKENS) to browse without stateful session
@router.post("/ghost")
async def ghost_access(request: Request, body: dict):
    token = body.get("ghost_token")
    rate_limit_check(request)
    if token in _GHOST_TOKENS:
        # create ephemeral admin jwt valid for short time
        jwt_token = create_jwt("admin", extra={"ghost": True}, exp_seconds=60 * 10)
        resp = JSONResponse({"status": "ok", "token": jwt_token})
        resp.set_cookie("session", jwt_token, httponly=True, secure=bool(getattr(config, "COOKIE_SECURE", False)))
        return resp
    raise HTTPException(status_code=403, detail="invalid ghost token")

# Admin-only dependency
def require_admin(request: Request):
    token = request.cookies.get("session") or request.headers.get("Authorization", "").split(" ")[-1]
    if not token:
        raise HTTPException(status_code=401)
    payload = verify_jwt(token)
    if payload.get("sub") != "admin":
        raise HTTPException(status_code=403)
    # check HWID lock if present
    if os.path.exists(".titan_hwid"):
        with open(".titan_hwid", "r") as f:
            hw = f.read().strip()
        if hw and hw != compute_local_hwid():
            raise HTTPException(status_code=403, detail="HWID mismatch")
    return payload

# Expose router for app integration
def get_router():
    return router

app = FastAPI(title="Titan-Glass Security Gate")
app.include_router(router)
