FROM python:3.12

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app

# تحديث النظام وتثبيت الأدوات الأساسية + Node.js
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        ca-certificates \
        git \
        ffmpeg \
        aria2 \
        unzip \
        build-essential && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# تثبيت pip باستخدام ensurepip
RUN python3 -m ensurepip && python3 -m pip install --upgrade pip setuptools wheel

# مسح أي كاش قديم
RUN pip cache purge || true
RUN rm -rf /usr/local/lib/python3.12/site-packages/*

# نسخ مكتبة pytgcalls المحلية أولاً
COPY pytgcalls /app/pytgcalls

# نسخ requirements واستبعاد pytgcalls
COPY requirements.txt /app/requirements.txt
RUN if [ -f /app/requirements.txt ]; then \
      grep -v -i '^py-tgcalls' /app/requirements.txt > /app/filtered-requirements.txt || true; \
    fi

# تثبيت المكتبات بدون كاش
RUN if [ -f /app/filtered-requirements.txt ]; then \
        pip install --no-cache-dir -r /app/filtered-requirements.txt; \
    fi && \
    pip install --no-cache-dir jinja2

# نسخ كل ملفات المشروع
COPY . /app

# تشغيل البوت
CMD ["python3", "run.py"]
