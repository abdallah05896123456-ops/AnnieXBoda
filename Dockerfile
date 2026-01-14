# ===============================
# Dockerfile AnnieXMedia (Fixed Git)
# ===============================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# تنظيف مسبق (بدون مسح ملفات الجيت لاحقاً)
RUN rm -rf /app/*

RUN apt-get update && \
    apt-get install -y --no-install-recommends git ffmpeg curl unzip build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    curl -fsSL https://deno.land/install.sh | sh && \
    ln -s /root/.deno/bin/deno /usr/local/bin/deno

COPY pytgcalls /app/pytgcalls

COPY requirements.txt /app/requirements.txt
RUN if [ -f /app/requirements.txt ]; then \
      grep -v -i '^py-tgcalls' /app/requirements.txt > /app/filtered-requirements.txt || true; \
    fi

RUN pip install --upgrade pip setuptools wheel && \
    if [ -f /app/filtered-requirements.txt ]; then \
        pip install --no-cache-dir -r /app/filtered-requirements.txt && \
        rm -rf /root/.cache/pip; \
    fi

# نسخ المشروع بالكامل (وهينسخ معاه مجلد .git المخفي)
COPY . /app

# ⚠️ شيلنا أمر حذف .git من هنا عشان البوت يلاقيه ويشتغل

CMD ["python3", "-m", "AnnieXMedia"]
