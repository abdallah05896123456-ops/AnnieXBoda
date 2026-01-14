# ===============================
# Dockerfile AnnieXMedia
# Python 3.12 مع pytgcalls محلي + FastAPI web
# ===============================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# تنظيف أي ملفات قديمة
RUN rm -rf /app/*

# تثبيت متطلبات النظام + deno
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ffmpeg curl unzip build-essential && \
    rm -rf /var/lib/apt/lists/* && \
    curl -fsSL https://deno.land/install.sh | sh && \
    ln -s /root/.deno/bin/deno /usr/local/bin/deno

# نسخ مكتبة pytgcalls المحلية أولاً
COPY pytgcalls /app/pytgcalls

# نسخ requirements.txt مع فلترة py-tgcalls
COPY requirements.txt /app/requirements.txt
RUN if [ -f /app/requirements.txt ]; then \
      grep -v -i '^py-tgcalls' /app/requirements.txt > /app/filtered-requirements.txt || true; \
    fi

# تثبيت باقي المكتبات
RUN pip install --upgrade pip setuptools wheel && \
    if [ -f /app/filtered-requirements.txt ]; then pip install --no-cache-dir -r /app/filtered-requirements.txt; fi

# نسخ كامل سورس AnnieXMedia
COPY . /app

# تأكيد استخدام pytgcalls المحلي
RUN python - <<'PY'
import pytgcalls, sys
print('PYTGCALLS_FROM=', getattr(pytgcalls,'__file__','<not found>'))
PY

# نقطة الدخول
CMD ["python3", "-m", "AnnieXMedia"]
