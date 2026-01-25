# 1. استخدام نسخة slim-bookworm (أكثر استقراراً وتوافقاً من slim العادية)
FROM python:3.12-slim-bookworm

# 2. تحسين أداء البايثون ومنع ملفات الكاش
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
# إعداد مسار Deno
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# 3. تحديث النظام وتثبيت الأساسيات + Node.js (مهم جداً لـ Music Bot)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        git \
        ffmpeg \
        aria2 \
        unzip \
        build-essential \
        python3-dev \
        libffi-dev \
        libxml2-dev \
        libxslt-dev \
        zlib1g-dev \
        gcc && \
    # تثبيت Node.js 20 (مهم لمكاتب التحميل مثل yt-dlp)
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    # تثبيت Deno
    curl -fsSL https://deno.land/install.sh | sh && \
    # تنظيف لتقليل الحجم
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 4. نسخ مكتبة pytgcalls المحلية (كما طلبت)
COPY pytgcalls /app/pytgcalls

# 5. معالجة requirements وحذف py-tgcalls منها لتجنب التعارض
COPY requirements.txt /app/requirements.txt
RUN if [ -f /app/requirements.txt ]; then \
      grep -v -i '^py-tgcalls' /app/requirements.txt > /app/filtered-requirements.txt || true; \
    fi

# 6. التثبيت: تحديث pip -> تثبيت المتطلبات -> تثبيت المكتبة المحلية
RUN pip install --upgrade pip setuptools wheel && \
    if [ -f /app/filtered-requirements.txt ]; then \
        pip install --no-cache-dir -r /app/filtered-requirements.txt; \
    fi && \
    # محاولة تثبيت المكتبة المحلية، وإذا فشلت (لأن المجلد فارغ) يتم التنبيه
    pip install --no-cache-dir ./pytgcalls || echo "⚠️ Warning: Local pytgcalls failed to install. Ensure the folder is not empty."

# 7. نسخ باقي ملفات البوت
COPY . /app

# 8. كود التحقق (اختياري للتأكد من مصدر المكتبة)
RUN python - <<'PY'
try:
    import pytgcalls
    print('✅ PYTGCALLS INSTALLED FROM:', getattr(pytgcalls, '__file__', 'Unknown'))
except ImportError:
    print('❌ PYTGCALLS NOT FOUND')
PY

# 9. أمر التشغيل
CMD ["python3", "run.py"]
