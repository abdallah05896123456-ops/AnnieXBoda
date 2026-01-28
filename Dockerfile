# -----------------------------------------------------
# المرحلة 1: استيراد محرك Ollama
# -----------------------------------------------------
FROM ollama/ollama:latest AS ollama_source

# -----------------------------------------------------
# المرحلة 2: نسختك المفضلة (بدون تعديل في السيستم)
# -----------------------------------------------------
FROM python:3.12-slim

# إعدادات البيئة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"
ENV TZ=Africa/Cairo

WORKDIR /app

# 1. (إضافة) نسخ محرك Ollama
COPY --from=ollama_source /usr/bin/ollama /usr/bin/ollama

# 2. تثبيت الأدوات (نفس أدواتك بالمللي + procps عشان نعرف نتحكم في التحميل)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git ffmpeg curl unzip build-essential python3-dev \
        libffi-dev libxml2-dev libxslt-dev zlib1g-dev gcc \
        aria2 procps ca-certificates tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    # تثبيت Node.js
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    # تثبيت Deno
    curl -fsSL https://deno.land/install.sh | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 3. تحديث أدوات بايثون
RUN pip install --upgrade pip setuptools wheel

# 4. نسخ مجلد pytgcalls
COPY pytgcalls /app/pytgcalls

# 5. تثبيت المكتبات
COPY requirements.txt .
RUN grep -v -i '^py-tgcalls\|pytgcalls' requirements.txt > filtered.txt && \
    pip install --no-cache-dir -r filtered.txt && \
    pip install pytz

# 6. 🔥 إعدادات yt-dlp الخاصة بك (زي ما هي ممنوع اللمس) 🔥
RUN mkdir -p /etc/yt-dlp && \
    echo "--remote-components ejs:github" > /etc/yt-dlp.conf

# 7. 🔥 تحميل وحش الكود (Qwen 2.5 32B - 19GB) 🔥
# ده أذكى وأشرس موديل كود حالياً (مش ديب سيك)
RUN (ollama serve > /dev/null 2>&1 &) && \
    sleep 10 && \
    ollama pull qwen2.5:32b && \
    pkill ollama

# 8. نسخ باقي الملفات
COPY . .

# 9. (تعديل) تشغيل start.sh عشان يقوم الذكاء والبوت سوا
RUN chmod +x start.sh
CMD ["./start.sh"]
