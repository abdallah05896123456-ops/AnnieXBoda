FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        ffmpeg \
        curl \
        unzip \
        gcc \
        g++ \
        make \
        build-essential \
        pkg-config \
        cmake \
        ninja-build \
        libffi-dev \
        libssl-dev \
        libopus-dev \
        libx11-6 \
        libx11-dev \
        libgl1 \
        libgl1-mesa-dev \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://deno.land/install.sh | sh \
    && ln -s /root/.deno/bin/deno /usr/local/bin/deno

WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python3", "-m", "AnnieXMedia"]
