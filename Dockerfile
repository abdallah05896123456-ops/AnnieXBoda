# 1. جلب سيرفر التيليجرام (المصدر الرسمي)
FROM aiogram/telegram-bot-api:latest AS server_source

# 2. استخدام بايثون نسخة Alpine عشان التوافق التام والسرعة
FROM python:3.12-alpine

# تحسينات البيئة لضمان السرعة القصوى
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# نسخ سيرفر التيليجرام (دلوقتي هيشتغل لأن البيئة متوافقة)
COPY --from=server_source /usr/local/bin/telegram-bot-api /usr/local/bin/telegram-bot-api

# 3. تثبيت الأدوات (نسخة Alpine)
RUN apk add --no-cache \
    git ffmpeg curl unzip build-essential python3-dev \
    libffi-dev aria2 nodejs npm libstdc++ \
    # تثبيت Deno لفك التشفير النووي
    && curl -fsSL https://deno.land/install.sh | sh

# 4. تثبيت مكتبات بايثون
RUN pip install --upgrade pip setuptools wheel
COPY pytgcalls /app/pytgcalls
COPY requirements.txt .
RUN grep -v -i '^py-tgcalls\|pytgcalls' requirements.txt > filtered.txt && \
    pip install --no-cache-dir -r filtered.txt

# 5. إعدادات yt-dlp الإجبارية
RUN mkdir -p /etc/yt-dlp && \
    echo "--remote-components ["ejs:github"]" > /etc/yt-dlp.conf

# 6. نسخ الملفات وصنع ملف التشغيل (اللي مش موجود عندك)
COPY . .
RUN printf "#!/bin/sh\n\
telegram-bot-api --local --api-id=\${API_ID} --api-hash=\${API_HASH} &\n\
sleep 5\n\
python3 run.py\n" > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# 8. انطلاق الصاروخ 🚀
CMD ["/app/entrypoint.sh"]
