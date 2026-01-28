# -----------------------------------------------------
# المرحلة الأولى: جلب Ollama من المصدر الرسمي (مضمون 100%)
# -----------------------------------------------------
FROM ollama/ollama:latest AS ollama_source

# -----------------------------------------------------
# المرحلة الثانية: بناء صورة البوت
# -----------------------------------------------------
FROM python:3.12-slim

# إعدادات البيئة وتحسين الأداء
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"
# ضبط توقيت السيرفر على القاهرة (عشان الأذان يظبط)
ENV TZ=Africa/Cairo

WORKDIR /app

# 1. نسخ ملف Ollama الأصلي من المرحلة الأولى (بدل التحميل والمشاكل)
COPY --from=ollama_source /usr/bin/ollama /usr/bin/ollama

# 2. تحديث النظام وتثبيت الأدوات
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git ffmpeg curl unzip build-essential python3-dev \
        libffi-dev libxml2-dev libxslt-dev zlib1g-dev gcc \
        aria2 procps ca-certificates tzdata && \
    # ضبط المنطقة الزمنية
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    # تثبيت Node.js
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    # تثبيت Deno
    curl -fsSL https://deno.land/install.sh | sh && \
    # تنظيف لتقليل الحجم
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 3. تحديث أدوات بايثون
RUN pip install --upgrade pip setuptools wheel

# 4. نسخ مجلد pytgcalls
COPY pytgcalls /app/pytgcalls

# 5. تثبيت المكتبات
COPY requirements.txt .
RUN grep -v -i '^py-tgcalls\|pytgcalls' requirements.txt > filtered.txt && \
    pip install --no-cache-dir -r filtered.txt

# 6. سحب الموديل (Mistral) وتجهيزه داخل الصورة
# (بما أن Ollama منسوخ من المصدر الرسمي، سيعمل فوراً)
RUN (ollama serve > /dev/null 2>&1 &) && \
    sleep 10 && \
    ollama pull mistral && \
    pkill ollama

# 7. إعدادات yt-dlp الإجبارية
RUN mkdir -p /etc/yt-dlp && \
    echo "--remote-components ejs:github" > /etc/yt-dlp.conf

# 8. نسخ باقي ملفات البوت
COPY . .

# 9. انطلاق الصاروخ 🚀 (تشغيل Ollama في الخلفية والبوت في الواجهة)
CMD bash -c "ollama serve > /dev/null 2>&1 & sleep 5 && python3 run.py"
