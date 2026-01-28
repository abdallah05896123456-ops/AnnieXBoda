# استخدام أحدث وأخف نسخة مستقرة من بايثون
FROM python:3.12-slim

# تحسينات الأداء للبيئة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# 1. تثبيت "محركات السرعة" وأدوات النظام + Ollama
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git ffmpeg curl unzip build-essential python3-dev \
        libffi-dev libxml2-dev libxslt-dev zlib1g-dev gcc \
        aria2 procps && \
    # تثبيت Node.js (المحرك 1 لفك التشفير)
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    # تثبيت Deno (المحرك 2 لفك التشفير)
    curl -fsSL https://deno.land/install.sh | sh && \
    # --- [ تثبيت Ollama الذكاء الاصطناعي ] ---
    curl -L https://ollama.com/download/ollama-linux-amd64 -o /usr/bin/ollama && \
    chmod +x /usr/bin/ollama && \
    # تنظيف المخلفات
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. تحديث أدوات بايثون الأساسية
RUN pip install --upgrade pip setuptools wheel

# 3. نسخ مجلد pytgcalls (النسخة المحلية المعدلة)
COPY pytgcalls /app/pytgcalls

# 4. تثبيت المكتبات (تأكد من وجود aiohttp في requirements.txt)
COPY requirements.txt .
RUN grep -v -i '^py-tgcalls\|pytgcalls' requirements.txt > filtered.txt && \
    pip install --no-cache-dir -r filtered.txt

# 5. تجهيز الموديل (Mistral) داخل الصورة لسرعة التشغيل
# بنشغل السيرفر مؤقتاً عشان نسحب الموديل ونقفله تاني أثناء البناء
RUN (ollama serve &) && sleep 5 && ollama pull mistral

# 6. إعدادات yt-dlp الإجبارية
RUN mkdir -p /etc/yt-dlp && \
    echo "--remote-components ejs:github" > /etc/yt-dlp.conf

# 7. نسخ باقي ملفات البوت
COPY . .

# 8. انطلاق الصاروخ 🚀 (تشغيل Ollama والبوت معاً)
CMD ollama serve & python3 run.py
