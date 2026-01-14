# ================================
# Dockerfile AnnieXMedia (Python 3.12 + pytgcalls local)
# ================================

# Python 3.12 Slim
FROM python:3.12-slim

# ----------------
# Environment variables
# ----------------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app

# ----------------
# تنظيف أي ملفات قديمة في حالة إعادة build
# ----------------
RUN rm -rf /app/*

# ----------------
# تثبيت متطلبات النظام + deno
# ----------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ffmpeg curl unzip build-essential net-tools && \
    rm -rf /var/lib/apt/lists/* && \
    curl -fsSL https://deno.land/install.sh | sh && \
    ln -s /root/.deno/bin/deno /usr/local/bin/deno

# ----------------
# نسخ مكتبة pytgcalls المحلية أولاً
# ----------------
COPY pytgcalls /app/pytgcalls

# ----------------
# نسخ requirements.txt مع فلترة py-tgcalls
# ----------------
COPY requirements.txt /app/requirements.txt
RUN if [ -f /app/requirements.txt ]; then \
      grep -v -i '^py-tgcalls' /app/requirements.txt > /app/filtered-requirements.txt || true; \
    fi

# ----------------
# تثبيت باقي المكتبات
# ----------------
RUN pip install --upgrade pip setuptools wheel && \
    if [ -f /app/filtered-requirements.txt ]; then pip install --no-cache-dir -r /app/filtered-requirements.txt; fi

# ----------------
# نسخ باقي سورس AnnieXMedia + web modules
# ----------------
COPY . /app

# ----------------
# تأكيد ان Python بيستخدم النسخة المحلية من pytgcalls
# ----------------
RUN python - <<'PY'
import pytgcalls
print('PYTGCALLS_FROM=', getattr(pytgcalls,'__file__','<not found>'))
PY

# ----------------
# نقطة الدخول
# ----------------
CMD ["python3", "-m", "AnnieXMedia"]
