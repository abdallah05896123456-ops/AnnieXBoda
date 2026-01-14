# ===============================
# Dockerfile AnnieXMedia (TitanOS Edition)
# ===============================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# 1. تحديث النظام وتثبيت ffmpeg و git
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ffmpeg curl unzip build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 2. تثبيت Deno (لو السورس معتمد عليه)
RUN curl -fsSL https://deno.land/install.sh | sh && \
    ln -s /root/.deno/bin/deno /usr/local/bin/deno

# 3. نسخ pytgcalls المعدل يدوياً (مهم جداً)
COPY pytgcalls /app/pytgcalls

# 4. تثبيت المكتبات (مع استبعاد pytgcalls عشان نستخدم النسخة المحلية)
COPY requirements.txt /app/requirements.txt
RUN if [ -f /app/requirements.txt ]; then \
      grep -v -i '^py-tgcalls' /app/requirements.txt > /app/filtered-requirements.txt || true; \
    fi

RUN pip install --upgrade pip setuptools wheel && \
    if [ -f /app/filtered-requirements.txt ]; then \
        pip install --no-cache-dir -r /app/filtered-requirements.txt && \
        rm -rf /root/.cache/pip; \
    fi

# 5. نسخ ملفات البوت بالكامل (بما فيها TitanOS و web_dashboard.py)
COPY . /app

# 🔥 6. فتح البورت للداشبورد (ده التعديل المهم) 🔥
EXPOSE 8080

# 7. أمر التشغيل
CMD ["python3", "-m", "AnnieXMedia"]
