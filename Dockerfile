# استخدام أحدث وأخف نسخة مستقرة من بايثون
FROM python:3.12-slim

# تحسينات الأداء للبيئة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# 1. تحديث النظام وتثبيت الأدوات الأساسية
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git ffmpeg curl unzip build-essential python3-dev \
        libffi-dev libxml2-dev libxslt-dev zlib1g-dev gcc \
        aria2 procps ca-certificates && \
    # تثبيت Node.js
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    # تثبيت Deno
    curl -fsSL https://deno.land/install.sh | sh && \
    # --- [ إصلاح تثبيت Ollama: التحميل من GitHub مباشرة ] ---
    curl -L "https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64" -o /usr/bin/ollama && \
    chmod +x /usr/bin/ollama && \
    # تنظيف المخلفات
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. تحديث أدوات بايثون الأساسية
RUN pip install --upgrade pip setuptools wheel

# 3. نسخ مجلد pytgcalls
COPY pytgcalls /app/pytgcalls

# 4. تثبيت المكتبات
COPY requirements.txt .
RUN grep -v -i '^py-tgcalls\|pytgcalls' requirements.txt > filtered.txt && \
    pip install --no-cache-dir -r filtered.txt

# 5. تجهيز الموديل (Mistral) داخل الصورة
# نقوم بتشغيل السيرفر في الخلفية، ننتظر قليلاً، نسحب الموديل، ثم نغلق السيرفر ليكتمل البناء
RUN (ollama serve > /dev/null 2>&1 &) && sleep 10 && ollama pull mistral && pkill ollama

# 6. إعدادات yt-dlp الإجبارية
RUN mkdir -p /etc/yt-dlp && \
    echo "--remote-components ejs:github" > /etc/yt-dlp.conf

# 7. نسخ باقي ملفات البوت
COPY . .

# 8. انطلاق الصاروخ 🚀 (تشغيل Ollama والبوت معاً)
CMD bash -c "ollama serve & sleep 5 && python3 run.py"
