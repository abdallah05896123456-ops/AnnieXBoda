# 1. استخدام نسخة مستقرة ومتوافقة
FROM python:3.12-slim-bookworm

# 2. إعدادات البيئة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

# 3. تثبيت الأدوات المساعدة و Node.js
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

# 5. التعامل مع المتطلبات
COPY requirements.txt .
# سنحذف أي إشارة لـ pytgcalls من المتطلبات لأننا سنستخدم النسخة التي معك
RUN sed -i '/pytgcalls/d' requirements.txt && \
    sed -i '/py-tgcalls/d' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# 6. تثبيت المكتبات الإجبارية التي يحتاجها كود pytgcalls ليعمل
# بما أننا لن نثبته بـ pip، يجب أن نوفر مكاتبه يدوياً
RUN pip install --no-cache-dir ntgcalls>=1.2.2 jinja2 pyrogram

# 7. نسخ كل ملفات المشروع (بما فيها مجلد pytgcalls)
COPY . .

# 8. تشغيل البوت
# ملاحظة: البوت سيتعرف على pytgcalls تلقائياً لأن المجلد موجود في نفس مسار run.py
CMD ["python3", "run.py"]
