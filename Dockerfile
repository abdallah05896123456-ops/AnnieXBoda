# استخدام نسخة slim فقط
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# 1. تحديث النظام وتثبيت الأساسيات + Node.js
# (Node.js ضروري عشان يوتيوب يشتغل، حتى لو الرابط معاك في المكتبات)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git ffmpeg curl unzip build-essential python3-dev \
        libffi-dev libxml2-dev libxslt-dev zlib1g-dev gcc && \
    # تثبيت Node.js الإصدار 20
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    # تثبيت Deno
    curl -fsSL https://deno.land/install.sh | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. تحديث pip
RUN pip install --upgrade pip setuptools wheel

# 3. نسخ مجلد pytgcalls المحلي
COPY pytgcalls /app/pytgcalls

# 4. تثبيت المكتبات من requirements.txt
# (سيتم تحميل ntgcalls و yt-dlp من الروابط الموجودة في ملفك)
COPY requirements.txt .
RUN grep -v -i '^py-tgcalls\|pytgcalls' requirements.txt > filtered.txt && \
    pip install --no-cache-dir -r filtered.txt

# 5. نسخ باقي ملفات المشروع
COPY . .

# 6. التشغيل
CMD ["python3", "run.py"]
