# 1. جلب سيرفر التيليجرام من المصدر الرسمي
FROM aiogram/telegram-bot-api:latest AS server_source

# 2. صورة البوت الأساسية (بايثون 3.12)
FROM python:3.12-slim

# تحسينات البيئة لضمان السرعة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# نسخ سيرفر التيليجرام لداخل البوت
COPY --from=server_source /usr/local/bin/telegram-bot-api /usr/local/bin/telegram-bot-api

# 3. تثبيت أدوات النظام والسرعة (Aria2, FFmpeg)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git ffmpeg curl unzip build-essential python3-dev \
        libffi-dev libxml2-dev libxslt-dev zlib1g-dev gcc \
        aria2 && \
    # تثبيت Node.js و Deno لفك التشفير
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    curl -fsSL https://deno.land/install.sh | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 4. تثبيت مكتبات بايثون
RUN pip install --upgrade pip setuptools wheel
COPY pytgcalls /app/pytgcalls
COPY requirements.txt .
RUN grep -v -i '^py-tgcalls\|pytgcalls' requirements.txt > filtered.txt && \
    pip install --no-cache-dir -r filtered.txt

# 5. إعدادات فك التشفير التلقائية لـ yt-dlp
RUN mkdir -p /etc/yt-dlp && \
    echo "--remote-components ejs:github" > /etc/yt-dlp.conf

# 6. نسخ الملفات
COPY . .

# 7. 🔥 الضربة القاضية: صنع ملف التشغيل برمجياً 🔥
# السطر ده هيخلق ملف entrypoint.sh من العدم عشان متبقاش محتاج ترفعه
RUN printf "#!/bin/bash\n\
telegram-bot-api --local --api-id=\${API_ID} --api-hash=\${API_HASH} &\n\
sleep 5\n\
python3 run.py\n" > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# 8. انطلاق الصاروخ 🚀
CMD ["/app/entrypoint.sh"]
