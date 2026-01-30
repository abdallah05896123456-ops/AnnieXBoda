# -----------------------------------------------------
# المرحلة الوحيدة: الكود بتاعك (g4f Edition - Clean)
# -----------------------------------------------------
# استخدام أحدث وأخف نسخة مستقرة من بايثون
FROM python:3.12-slim

# تحسينات الأداء للبيئة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# 1. تثبيت "محركات السرعة" وأدوات النظام
# (شيلنا procps لأننا مش محتاجين نعمل mount للرامات خلاص)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git ffmpeg curl unzip build-essential python3-dev \
        libffi-dev libxml2-dev libxslt-dev zlib1g-dev gcc \
        aria2 && \
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

# 🔥 إضافة مهمة: تثبيت محرك الذكاء الجديد (g4f) 🔥
RUN pip install -U g4f curl_cffi

# 5. إعدادات yt-dlp الإجبارية
RUN mkdir -p /etc/yt-dlp && \
    echo "--remote-components ejs:github" > /etc/yt-dlp.conf

# 6. نسخ باقي ملفات البوت
COPY . .

# 7. انطلاق الصاروخ 🚀
RUN chmod +x start.sh
CMD ["./start.sh"]
