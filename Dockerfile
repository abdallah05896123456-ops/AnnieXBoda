# 1. استخدام نسخة Slim خفيفة بناءً على طلبك (من السورس الثاني)
FROM python:3.12-slim

# إعدادات البيئة لتحسين الأداء
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
# إعدادات Deno (من السورس الثاني)
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# 2. تحديث النظام وتثبيت الأدوات المدمجة (الأساسية + Node.js + Deno)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        git \
        ffmpeg \
        aria2 \
        unzip \
        build-essential \
        # نحتاج المكتبات دي عشان بايثون يعرف يبني الملفات في نسخة slim
        libffi-dev \
        libxml2-dev \
        libxslt-dev \
        zlib1g-dev \
        gcc && \
    # تثبيت Node.js 20 (مهم عشان yt-dlp ومشاكل يوتيوب)
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    # تثبيت Deno (من السورس الثاني اللي طلبته)
    curl -fsSL https://deno.land/install.sh | sh && \
    # تنظيف المخلفات عشان الصورة تفضل Slim
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 3. تحديث pip
RUN pip install --upgrade pip setuptools wheel

# 4. نسخ مكتبة pytgcalls المحلية (من السورس بتاعك)
COPY pytgcalls /app/pytgcalls

# 5. معالجة ملف المتطلبات واستبعاد pytgcalls (من السورس بتاعك)
COPY requirements.txt /app/requirements.txt
RUN if [ -f /app/requirements.txt ]; then \
      grep -v -i '^py-tgcalls' /app/requirements.txt > /app/filtered-requirements.txt || true; \
    fi

# 6. تثبيت المكتبات
RUN if [ -f /app/filtered-requirements.txt ]; then \
        pip install --no-cache-dir -r /app/filtered-requirements.txt; \
    fi && \
    # تثبيت المكتبة المحلية
    pip install --no-cache-dir ./pytgcalls && \
    pip install --no-cache-dir jinja2

# 7. نسخ باقي الملفات
COPY . /app

# 8. أمر التشغيل الخاص بيك (بدون تعديل)
CMD ["python3", "run.py"]
