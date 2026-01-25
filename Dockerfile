FROM python:3.12-slim

# تحسينات الأداء
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
# إضافة المجلد الحالي لمسار البايثون لضمان قراءة pytgcalls
ENV PYTHONPATH="${PYTHONPATH}:/app"
# إعداد Deno
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# 1. تحديث النظام وتثبيت Node.js و ffmpeg
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
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. نسخ مكتبة pytgcalls (نسخ فقط بدون تثبيت via pip)
COPY pytgcalls /app/pytgcalls

# 3. معالجة requirements.txt وحذف py-tgcalls منها
COPY requirements.txt /app/requirements.txt
RUN if [ -f /app/requirements.txt ]; then \
      grep -v -i '^py-tgcalls' /app/requirements.txt > /app/filtered-requirements.txt || true; \
    fi

# 4. تثبيت المكتبات الخارجية
# ملاحظة هامة: أضفنا ntgcalls يدوياً لأننا لم نثبت pytgcalls عبر pip
RUN pip install --upgrade pip setuptools wheel && \
    if [ -f /app/filtered-requirements.txt ]; then \
        pip install --no-cache-dir -r /app/filtered-requirements.txt; \
    fi && \
    # تثبيت الاعتماديات الضرورية لعمل النسخة المحلية
    pip install --no-cache-dir ntgcalls>=1.2.2 jinja2

# 5. نسخ باقي ملفات البوت
COPY . /app

# 6. تشغيل البوت
CMD ["python3", "run.py"]
