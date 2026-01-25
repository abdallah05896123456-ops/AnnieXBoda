# استخدام نسخة slim
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# 1. تحديث النظام وتثبيت الأساسيات + Node.js + Deno
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git ffmpeg curl unzip build-essential python3-dev \
        libffi-dev libxml2-dev libxslt-dev zlib1g-dev gcc && \
    # تثبيت Node.js
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    # تثبيت Deno
    curl -fsSL https://deno.land/install.sh | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. تحديث pip
RUN pip install --upgrade pip setuptools wheel

# 3. نسخ مجلد pytgcalls المحلي
COPY pytgcalls /app/pytgcalls

# 4. تثبيت المكتبات من ملفك
COPY requirements.txt .
RUN grep -v -i '^py-tgcalls\|pytgcalls' requirements.txt > filtered.txt && \
    pip install --no-cache-dir -r filtered.txt

# 🔥 5. (الحل السحري) إجبار yt-dlp على تحميل أدوات فك التشفير تلقائياً 🔥
# هذا السطر ينشئ ملف إعدادات يحل مشكلة Signature solving failed
RUN echo "--remote-components ejs:github" > /etc/yt-dlp.conf

# 6. نسخ باقي ملفات المشروع
COPY . .

# 7. التشغيل
CMD ["python3", "run.py"]
