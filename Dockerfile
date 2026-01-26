# 1. جلب سيرفر التيليجرام من المصدر
FROM aiogram/telegram-bot-api:latest AS server_source

# 2. العودة لنسخة Slim المستقرة التي تطلبها
FROM python:3.12-slim

# تحسينات الأداء للبيئة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# نسخ سيرفر التيليجرام
COPY --from=server_source /usr/local/bin/telegram-bot-api /usr/local/bin/telegram-bot-api

# 3. تثبيت أدوات النظام (Debian Slim)
# تم إضافة 'musl' لحل مشكلة 'required file not found' للسيرفر
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git ffmpeg curl unzip build-essential python3-dev \
        libffi-dev libxml2-dev libxslt-dev zlib1g-dev gcc \
        aria2 musl && \
    # تثبيت Node.js و Deno
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    curl -fsSL https://deno.land/install.sh | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 4. تحديث أدوات بايثون وتثبيت المكتبات
RUN pip install --upgrade pip setuptools wheel
COPY pytgcalls /app/pytgcalls
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. إعدادات فك التشفير التلقائية لـ yt-dlp
RUN mkdir -p /etc/yt-dlp && \
    echo "--remote-components ejs:github" > /etc/yt-dlp.conf

# 6. نسخ الملفات وصنع ملف التشغيل أوتوماتيكياً
COPY . .

# حل مشكلة الـ Binary عبر عمل Link لمكتبة musl داخل Debian
RUN ln -s /usr/lib/x86_64-linux-musl/libc.so /lib/ld-musl-x86_64.so.1

RUN printf "#!/bin/bash\n\
telegram-bot-api --local --api-id=\${API_ID} --api-hash=\${API_HASH} &\n\
sleep 5\n\
python3 run.py\n" > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# 7. انطلاق الصاروخ 🚀
CMD ["/app/entrypoint.sh"]
