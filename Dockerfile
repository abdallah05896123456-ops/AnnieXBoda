# 1. استخدام صورة مستقرة
FROM python:3.12-slim-bookworm

# 2. إعدادات البيئة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# 3. تحديث النظام وتثبيت Node.js والملحقات
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl git ffmpeg aria2 unzip build-essential python3-dev \
        libffi-dev libxml2-dev libxslt-dev zlib1g-dev gcc && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    curl -fsSL https://deno.land/install.sh | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 4. تحديث pip
RUN pip install --upgrade pip setuptools wheel

# 5. تثبيت المتطلبات (مع تجاهل pytgcalls لأننا نملكه محلياً)
COPY requirements.txt .
RUN sed -i '/pytgcalls/d' requirements.txt && \
    sed -i '/py-tgcalls/d' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# 6. تثبيت المكاتب المساعدة للكود المحلي
RUN pip install --no-cache-dir ntgcalls>=1.2.2 jinja2 pyrogram

# 7. نسخ ملفات المشروع
COPY . .

# 🔥 8. الإصلاح السحري: تعديل كود pytgcalls المحلي ليتوافق مع Pyrogram الجديد 🔥
# هذا الأمر يستبدل الخطأ المحذوف (GroupcallForbidden) بالخطأ العام (Forbidden)
RUN sed -i 's/from pyrogram.errors import GroupcallForbidden/from pyrogram.errors import Forbidden as GroupcallForbidden/g' /app/pytgcalls/mtproto/pyrogram_client.py

# 9. تشغيل البوت
CMD ["python3", "run.py"]
