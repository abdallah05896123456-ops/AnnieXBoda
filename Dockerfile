# ---------- STAGE 1: Builder (build wheels) ----------
FROM python:3.11-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# تثبيت أدوات البناء والـ libs اللازمة لبناء الحزم (ntgcalls/wrtc/mesa...)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      gcc \
      g++ \
      make \
      cmake \
      ninja-build \
      pkg-config \
      git \
      curl \
      unzip \
      ca-certificates \
      libffi-dev \
      libssl-dev \
      libopus-dev \
      libx11-dev \
      libgl1-mesa-dev \
      ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# انسخ فقط requirements عشان نستفيد من Docker cache
COPY requirements.txt /build/requirements.txt

# جهّز pip وبنِيّ wheels (يشمَل git deps). الناتج في /wheels
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---------- STAGE 2: Runtime (final smaller image) ----------
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# حزم runtime فقط (خفيفة نسبياً)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libffi-dev \
      libssl-dev \
      libopus0 \
      libx11-6 \
      libgl1 \
      ffmpeg \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# انسخ wheels من الـ builder وثبتهم (أسرع وأكثر موثوقية من build وقت التشغيل)
COPY --from=builder /wheels /wheels
COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt

# انسخ الكود
COPY . /app

# أنشئ مستخدم غير root وشغّل تحت حسابه
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# لو يحتاج exposed port: EXPOSE 8080
# EXPOSE 8080

# عدّل الأمر النهائي حسب مشروعك
CMD ["python3", "-m", "AnnieXMedia"]
