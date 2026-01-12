# Recommended: Python 3.12 for pytgcalls local setup
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# system deps + deno (keep your original tooling)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ffmpeg curl unzip build-essential && \
    rm -rf /var/lib/apt/lists/* && \
    curl -fsSL https://deno.land/install.sh | sh && \
    ln -s /root/.deno/bin/deno /usr/local/bin/deno

# Copy local pytgcalls first (this ensures Python will import local package)
# Make sure you have the folder pytgcalls/ in the repo root.
COPY pytgcalls /app/pytgcalls

# Copy requirements and filter out any py-tgcalls entries so pip won't install it
COPY requirements.txt /app/requirements.txt
RUN if [ -f /app/requirements.txt ]; then \
      grep -v -i '^py-tgcalls' /app/requirements.txt > /app/filtered-requirements.txt || true; \
    fi

# Install remaining deps
RUN pip install --upgrade pip setuptools wheel && \
    if [ -f /app/filtered-requirements.txt ]; then pip install --no-cache-dir -r /app/filtered-requirements.txt; fi

# Copy rest of source
COPY . /app

# Verify that the local pytgcalls is used
RUN python - <<'PY'
import pytgcalls, sys
print('PYTGCALLS_FROM=', getattr(pytgcalls,'__file__','<not found>'))
PY

# Clean old data if exists (optional, ensures clean build on fly.io)
RUN rm -rf /app/__pycache__ /app/*.pyc /app/*.pyo

# Keep same entrypoint
CMD ["python3", "-m", "AnnieXMedia"]
