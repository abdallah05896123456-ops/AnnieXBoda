# ==============================================================================
# Dockerfile AnnieXMedia (TitanOS Ultimate Edition)
# Complete Fresh Rebuild + Cache Clean + Node.js + Python 3.12
# ==============================================================================

FROM python:3.12-slim

# ===============================
# إعدادات البيئة
# ===============================
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app

# ===============================
# [1] تحديث النظام وتثبيت الأدوات
# ===============================
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        ca-certificates \
        git \
        ffmpeg \
        aria2 \
        unzip \
        build-essential && \
    # تثبيت Node.js 20
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    # تنظيف كل شيء
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ===============================
# [2] مسح أي تثبيت بايثون سابق
# ===============================
RUN pip cache purge || true
RUN rm -rf /usr/local/lib/python3.12/site-packages/*

# ===============================
# [3] نسخ مكتبة pytgcalls المحلية أولاً
# ===============================
COPY pytgcalls /app/pytgcalls

# ===============================
# [4] نسخ ملف requirements.txt واستبعاد pytgcalls
# ===============================
COPY requirements.txt /app/requirements.txt
RUN if [ -f /app/requirements.txt ]; then \
      grep -v -i '^py-tgcalls' /app/requirements.txt > /app/filtered-requirements.txt || true; \
    fi

# ===============================
# [5] تثبيت كل مكتبات بايثون من الصفر بدون كاش
# ===============================
RUN pip install --upgrade pip setuptools wheel && \
    if [ -f /app/filtered-requirements.txt ]; then \
        pip install --no-cache-dir -r /app/filtered-requirements.txt; \
    fi && \
    pip install --no-cache-dir jinja2

# ===============================
# [6] نسخ كل ملفات المشروع
# ===============================
COPY . /app

# ===============================
# [7] فتح المنفذ وتشغيل البوت عبر run.py
# ===============================
# EXPOSE 8080
CMD ["python3", "run.py"]
