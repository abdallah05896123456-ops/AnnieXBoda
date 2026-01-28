# -----------------------------------------------------
# المرحلة 1: المصدر الرسمي (Ollama)
# -----------------------------------------------------
FROM ollama/ollama:latest AS ollama_source

# -----------------------------------------------------
# المرحلة 2: صورة البوت (The Beast - 40GB Version)
# -----------------------------------------------------
FROM python:3.12-slim

# إعدادات البيئة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV TZ=Africa/Cairo

WORKDIR /app

# 1. نسخ Ollama
COPY --from=ollama_source /usr/bin/ollama /usr/bin/ollama

# 2. تحديث النظام والأدوات
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git ffmpeg curl unzip build-essential python3-dev \
        libffi-dev libxml2-dev libxslt-dev zlib1g-dev gcc \
        aria2 procps ca-certificates tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    curl -fsSL https://deno.land/install.sh | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 3. بايثون
RUN pip install --upgrade pip setuptools wheel

# 4. نسخ pytgcalls
COPY pytgcalls /app/pytgcalls

# 5. المكتبات + (إصلاح pytz)
COPY requirements.txt .
RUN grep -v -i '^py-tgcalls\|pytgcalls' requirements.txt > filtered.txt && \
    pip install --no-cache-dir -r filtered.txt && \
    pip install pytz

# 6. 🔥 تحميل الوحش (Llama 3 70B - حجم 40 جيجا) 🔥
# انتبه: هذه الخطوة ستستغرق وقتاً طويلاً في التحميل
RUN (ollama serve > /dev/null 2>&1 &) && \
    sleep 10 && \
    ollama pull llama3:70b && \
    pkill ollama

# 7. إعدادات يوتيوب
RUN mkdir -p /etc/yt-dlp && \
    echo "--remote-components ejs:github" > /etc/yt-dlp.conf

# 8. نسخ الملفات
COPY . .

# 9. التشغيل عبر start.sh (ضروري جداً لهذه النسخة الثقيلة)
RUN chmod +x start.sh
CMD ["./start.sh"]
