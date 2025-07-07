# ---------------------------
# 📦 backend/Dockerfile - FastAPI
# ---------------------------
    FROM python:3.11-slim

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
    CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]