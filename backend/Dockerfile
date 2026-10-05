# ---------------------------
# 📦 backend/Dockerfile - FastAPI
# ---------------------------
# ---------------------------------------------------
# STAGE 1 : Builder (Isolé - ne sera pas dans l'image finale)
# ---------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir --upgrade uv

COPY requirements.txt ./

# Création du venv et installation des dépendances Python
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install --upgrade -r requirements.txt

# ---------------------------------------------------
# STAGE 2 : Final Runtime (Image de production)
# ---------------------------------------------------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# 1. Certificats CA (requis pour TLS/Mongo Atlas) + Mise à jour de sécurité de l'OS
RUN apt-get update && apt-get dist-upgrade -y \
    && apt-get install -y --no-install-recommends ca-certificates \
    && update-ca-certificates \
    && apt-get purge -y linux-libc-dev \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copie uniquement de l'environnement virtuel pré-construit (sans tools de build)
COPY --from=builder /opt/venv /opt/venv
COPY . .

# Utilisateur non-root
RUN useradd -u 1000 -m appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
