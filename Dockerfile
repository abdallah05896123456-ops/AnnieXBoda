# -------------------------------
# Dockerfile for AnnieXMedia Full Setup
# Python 3.12 + Node.js (for frontend build)
# -------------------------------

# استخدم نسخة Python 3.12 slim
FROM python:3.12-slim

# -------------------------------
# إعداد البيئة
# -------------------------------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app

# تنظيف أي ملفات قديمة
RUN rm -rf /app/*

# -------------------------------
# تثبيت الأدوات النظامية
# -------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git ffmpeg curl unzip build-essential \
        nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# -------------------------------
# تثبيت deno (اختياري للـ frontend scripts)
# -------------------------------
RUN curl -fsSL https://deno.land/install.sh | sh && \
    ln -s /root/.deno/bin/deno /usr/local/bin/deno

# -------------------------------
# نسخ مكتبة pytgcalls المحلية أولاً
# -------------------------------
COPY pytgcalls /app/pytgcalls

# -------------------------------
# نسخ requirements.txt مع فلترة py-tgcalls
# -------------------------------
COPY requirements.txt /app/requirements.txt
RUN if [ -f /app/requirements.txt ]; then \
        grep -v -i '^py-tgcalls' /app/requirements.txt > /app/filtered-requirements.txt || true; \
    fi

# -------------------------------
# تثبيت مكتبات Python
# -------------------------------
RUN pip install --upgrade pip setuptools wheel && \
    if [ -f /app/filtered-requirements.txt ]; then pip install --no-cache-dir -r /app/filtered-requirements.txt; fi

# -------------------------------
# نسخ باقي سورس AnnieXMedia
# -------------------------------
COPY . /app

# -------------------------------
# Build frontend (React/Vite) لو موجود
# -------------------------------
RUN if [ -d "/app/web" ]; then \
        cd /app/web && \
        if [ -f "package.json" ]; then \
            npm install && \
            npm run build; \
        fi \
    ; fi

# -------------------------------
# تأكيد ان Python بيستخدم النسخة المحلية من pytgcalls
# -------------------------------
RUN python - <<'PY'
import pytgcalls, sys
print('PYTGCALLS_FROM=', getattr(pytgcalls,'__file__','<not found>'))
PY

# -------------------------------
# نقطة الدخول
# -------------------------------
CMD ["python3", "-m", "AnnieXMedia"]
