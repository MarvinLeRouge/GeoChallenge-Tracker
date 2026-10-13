# ---------------------------
# 📦 backend/Dockerfile - FastAPI
# ---------------------------

# ---------------------------------------------------
# STAGE 1: builder - installs Python deps in a venv, isolated from the final image.
# build-essential (and the linux-libc-dev headers it pulls in) never reach the
# runtime image this way.
# ---------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY requirements.txt ./
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install -r requirements.txt

# ---------------------------------------------------
# STAGE 2: runtime - lean final image, no build tools.
# ---------------------------------------------------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# ca-certificates: root CA for TLS (Mongo Atlas). curl: docker-compose healthcheck.
# dist-upgrade: pulls in available OS security patches.
RUN apt-get update && apt-get dist-upgrade -y \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && update-ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY . .

# Non-root user (UID 1000, matches shared/backups and shared/uploads ownership on the VPS)
RUN useradd -u 1000 -m appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
