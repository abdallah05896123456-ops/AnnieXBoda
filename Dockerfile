# ==============================================================================
# Dockerfile AnnieXMedia (TitanOS Ultimate Edition)
# Optimized for Web Dashboard + Music Bot Bridge + YouTube JS Solver
# ==============================================================================

FROM python:3.12-slim

# إعدادات البيئة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# ------------------------------------------------------------------------------
# [1] تحديث النظام وتثبيت Node.js (الحل السحري لمشكلة 403)
# ------------------------------------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    ca-certificates && \
    # تثبيت Node.js 20 (أفضل من Deno لـ yt-dlp)
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    # تثبيت باقي الحزم
    apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    aria2 \
    unzip \
    build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ------------------------------------------------------------------------------
# [2] نسخ مجلد pytgcalls المحلي
# ------------------------------------------------------------------------------
COPY pytgcalls /app/pytgcalls

# ------------------------------------------------------------------------------
# [3] تثبيت مكتبات بايثون
# ------------------------------------------------------------------------------
COPY requirements.txt /app/requirements.txt

# استبعاد pytgcalls من الملف لأنه موجود محلياً
RUN if [ -f /app/requirements.txt ]; then \
      grep -v -i '^py-tgcalls' /app/requirements.txt > /app/filtered-requirements.txt || true; \
    fi

# تحديث pip وتثبيت المتطلبات + (jinja2)
RUN pip install --upgrade pip setuptools wheel && \
    if [ -f /app/filtered-requirements.txt ]; then \
        pip install --no-cache-dir -r /app/filtered-requirements.txt; \
    fi && \
    pip install --no-cache-dir jinja2

# ------------------------------------------------------------------------------
# [4] نسخ ملفات المشروع بالكامل
# ------------------------------------------------------------------------------
COPY . /app

# ------------------------------------------------------------------------------
# [5] فتح المنفذ وتشغيل البوت عبر المحرك النفاث (run.py)
# ------------------------------------------------------------------------------
EXPOSE 8080

# ✅ التعديل هنا: تشغيل run.py بدلاً من الموديول المباشر لتفعيل uvloop
CMD ["python3", "run.py"]
