# 1. جلب سيرفر التيليجرام الرسمي (متوافق مع Alpine)
FROM aiogram/telegram-bot-api:latest AS server_source

# 2. صورة البوت الأساسية (Alpine لضمان السرعة والتوافق)
FROM python:3.12-alpine

# تحسينات الأداء للبيئة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# نسخ سيرفر التيليجرام لداخل المجلد (دلوقتي هيشتغل فوراً)
COPY --from=server_source /usr/local/bin/telegram-bot-api /usr/local/bin/telegram-bot-api

# 3. تثبيت الأدوات (نسخة Alpine)
RUN apk add --no-cache \
    git ffmpeg curl unzip build-base python3-dev \
    libffi-dev aria2 nodejs npm libstdc++ gcompat \
    && curl -fsSL https://deno.land/install.sh | sh

# 4. تثبيت مكتبات بايثون
RUN pip install --upgrade pip setuptools wheel
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. إنشاء ملف التشغيل تلقائياً (لحل مشكلة الملف المفقود)
RUN printf "#!/bin/sh\n\
telegram-bot-api --local --api-id=\${API_ID} --api-hash=\${API_HASH} &\n\
sleep 5\n\
python3 run.py\n" > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# 6. نسخ باقي ملفات البوت
COPY . .

# 7. انطلاق الصاروخ النووي 🚀
CMD ["/app/entrypoint.sh"]
