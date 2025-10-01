# ---------------------------
# 📦 backend/Dockerfile - FastAPI
# ---------------------------
    FROM python:3.11-slim

    ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

    # 👇 IMPORTANT: certifs racine pour TLS (Mongo Atlas)
    RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl build-essential \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

    # Création du dossier de l’app
    WORKDIR /app
    
    # Installer uv
    RUN pip install uv

    # Copier le fichier pyproject et installer les deps
    COPY requirements.txt ./
    RUN uv pip install -r requirements.txt --system

    # Copie du code source
    COPY . .
    
    # Commande de lancement
    CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]