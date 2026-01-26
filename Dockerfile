# استخدام أحدث وأخف نسخة مستقرة من بايثون
FROM python:3.12-slim

# تحسينات الأداء للبيئة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# تثبيت محركات السرعة وأدوات النظام + سيرفر التيليجرام المحلي
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git ffmpeg curl unzip build-essential python3-dev \
        libffi-dev libxml2-dev libxslt-dev zlib1g-dev gcc \
        aria2 telegram-bot-api && \
    # تثبيت Node.js و Deno لفك التشفير
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    curl -fsSL https://deno.land/install.sh | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel

COPY pytgcalls /app/pytgcalls
COPY requirements.txt .
RUN grep -v -i '^py-tgcalls\|pytgcalls' requirements.txt > filtered.txt && \
    pip install --no-cache-dir -r filtered.txt

# إعدادات yt-dlp الإجبارية لفك التشفير تلقائياً
RUN mkdir -p /etc/yt-dlp && \
    echo "--remote-components ejs:github" > /etc/yt-dlp.conf

COPY . .

# منح صلاحية التنفيذ لسكربت التشغيل
RUN chmod +x entrypoint.sh

# انطلاق الصاروخ النووي عبر سكربت التشغيل المزدوج
CMD ["./entrypoint.sh"]
