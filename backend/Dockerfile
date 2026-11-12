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

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/

# Use the image's own Python, install only runtime deps from the lock into /opt/venv.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

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

# The app runs entirely from /opt/venv (see PATH above); the base image's own
# system-level pip/setuptools/wheel are never imported at runtime. Removing
# them drops two CVEs (wheel itself, and jaraco.context vendored inside
# setuptools) with no functional impact.
RUN /usr/local/bin/python3 -m pip uninstall -y pip setuptools wheel

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY . .

# Non-root user (UID 1000, matches shared/backups and shared/uploads ownership on the VPS)
RUN useradd -u 1000 -m appuser && chown -R appuser:appuser /app
USER appuser

# No --reload here: this image runs in production. Dev compose adds it via `command:`.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
