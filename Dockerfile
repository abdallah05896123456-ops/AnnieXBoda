# ===============================
# Dockerfile AnnieXMedia (Nested Web Structure)
# ===============================

FROM python:3.12-slim

# إعدادات تقليل الكاش ومنع ملفات .pyc
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# 1. تنظيف مسبق (Aggressive Clean Start)
RUN rm -rf /app/*

# 2. تحديث النظام وتثبيت Deno + ffmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ffmpeg curl unzip build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    curl -fsSL https://deno.land/install.sh | sh && \
    ln -s /root/.deno/bin/deno /usr/local/bin/deno

# 3. نسخ مكتبة pytgcalls المحلية (الأولوية لها)
COPY pytgcalls /app/pytgcalls

# 4. نسخ requirements.txt وفلترة المكتبة المتعارضة
COPY requirements.txt /app/requirements.txt
RUN if [ -f /app/requirements.txt ]; then \
      grep -v -i '^py-tgcalls' /app/requirements.txt > /app/filtered-requirements.txt || true; \
    fi

# 5. تثبيت المكتبات مع مسح الكاش فوراً
RUN pip install --upgrade pip setuptools wheel && \
    if [ -f /app/filtered-requirements.txt ]; then \
        pip install --no-cache-dir -r /app/filtered-requirements.txt && \
        rm -rf /root/.cache/pip; \
    fi

# 6. نسخ المشروع بالكامل
# ⚠️ هذا الأمر هينسخ فولدر AnnieXMedia وبداخله فولدر web تلقائياً
COPY . /app

# 7. تنظيف نهائي لما بعد النسخ
# بيمسح أي كاش بايثون قديم جاي من جهازك
RUN find . -type d -name "__pycache__" -exec rm -rf {} + && \
    rm -rf .git .github

# 8. نقطة التشغيل
CMD ["python3", "-m", "AnnieXMedia"]
