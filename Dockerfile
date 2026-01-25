# استخدام نسخة slim-bookworm الأفضل والأخف (متوافقة مع كل المكتبات)
FROM python:3.12-slim-bookworm

# تحسين أداء البايثون
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
# إعدادات Deno
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# 1. تحديث النظام وتثبيت الأساسيات + Node.js 20 (للتعامل مع يوتيوب)
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
    # تثبيت Node.js 20
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    # تثبيت Deno
    curl -fsSL https://deno.land/install.sh | sh && \
    # تنظيف
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. تحديث pip
RUN pip install --upgrade pip setuptools wheel

# 3. نسخ مكتبة pytgcalls المحلية (بدون تثبيت)
# النسخ لوحده كفاية عشان البوت يشوفها
COPY pytgcalls /app/pytgcalls

# 4. معالجة requirements وحذف py-tgcalls القديمة
COPY requirements.txt /app/requirements.txt
RUN if [ -f /app/requirements.txt ]; then \
      grep -v -i '^py-tgcalls' /app/requirements.txt > /app/filtered-requirements.txt |

| true; \
    fi

# 5. تثبيت المكتبات
# 🔥 التعديل هنا: شلنا تثبيت المجلد المحلي، وضفنا ntgcalls يدوياً 🔥
RUN if [ -f /app/filtered-requirements.txt ]; then \
        pip install --no-cache-dir -r /app/filtered-requirements.txt; \
    fi && \
    # نثبت ntgcalls لأننا لغينا تثبيت pytgcalls الأوتوماتيكي
    pip install --no-cache-dir ntgcalls>=1.2.2 jinja2

# 6. نسخ باقي ملفات البوت
COPY. /app

# 7. تشغيل البوت
CMD ["python3", "run.py"]
