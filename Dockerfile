# -----------------------------------------------------
# المرحلة 1: استيراد محرك Ollama (الإضافة الوحيدة)
# -----------------------------------------------------
FROM ollama/ollama:latest AS ollama_source

# -----------------------------------------------------
# المرحلة 2: الكود بتاعك (بدون أي تغيير)
# -----------------------------------------------------
# استخدام أحدث وأخف نسخة مستقرة من بايثون
FROM python:3.12-slim

# تحسينات الأداء للبيئة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"
# (إضافة) تحديد مسار الموديلات عشان تتخزن في الرامات
ENV OLLAMA_MODELS="/root/.ollama/models"

WORKDIR /app

# (إضافة) نسخ محرك Ollama لداخل نسختك
COPY --from=ollama_source /usr/bin/ollama /usr/bin/ollama

# 1. تثبيت "محركات السرعة" وأدوات النظام
# - aria2: عشان السرعة الجنونية (أهم حاجة كانت ناقصة).
# - nodejs & deno: عشان فك تشفير يوتيوب الجديد.
# - ffmpeg: عشان معالجة الصوت والفيديو.
# (إضافة صغيرة: procps عشان نعرف نعمل mount للرامات)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git ffmpeg curl unzip build-essential python3-dev \
        libffi-dev libxml2-dev libxslt-dev zlib1g-dev gcc \
        aria2 procps && \
    # تثبيت Node.js (المحرك 1 لفك التشفير)
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    # تثبيت Deno (المحرك 2 لفك التشفير - مهم جداً حالياً)
    curl -fsSL https://deno.land/install.sh | sh && \
    # تنظيف المخلفات لتقليل حجم الصورة
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. تحديث أدوات بايثون الأساسية
RUN pip install --upgrade pip setuptools wheel

# 3. نسخ مجلد pytgcalls (النسخة المحلية المعدلة)
COPY pytgcalls /app/pytgcalls

# 4. تثبيت المكتبات (مع استثناء pytgcalls لتجنب التعارض)
COPY requirements.txt .
RUN grep -v -i '^py-tgcalls\|pytgcalls' requirements.txt > filtered.txt && \
    pip install --no-cache-dir -r filtered.txt

# 5. 🔥 الضربة القاضية: إعدادات yt-dlp الإجبارية 🔥
# هذا السطر يجبر البوت على تحميل أدوات فك التشفير تلقائياً دون انتظار إذن
RUN mkdir -p /etc/yt-dlp && \
    echo "--remote-components ejs:github" > /etc/yt-dlp.conf

# 6. نسخ باقي ملفات البوت
COPY . .

# 7. انطلاق الصاروخ 🚀
# (تعديل) لازم نشغل start.sh عشان يعمل الرام ديسك ويشغل الذكاء
RUN chmod +x start.sh
CMD ["./start.sh"]
