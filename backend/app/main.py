# backend/app/main.py

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import (
    run_in_threadpool,
)  # optionnel mais propre si fonctions sync

from app.api.routes import routers
from app.core.middleware import MaxBodySizeMiddleware
from app.core.settings import get_settings
settings = get_settings()
from app.db.seed_data import seed_referentials
from app.db.seed_indexes import ensure_indexes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    # Si ensure_indexes / seed_referentials sont synchrones, on peut les déporter dans un thread
    await run_in_threadpool(ensure_indexes)  # toujours

    if os.getenv("SEED_ON_STARTUP", "false").lower() == "true":
        await run_in_threadpool(seed_referentials)  # idempotent et léger

    yield  # l'app tourne ici

    # --- shutdown ---
    # rien pour le moment


app = FastAPI(title="GeoChallenge API", lifespan=lifespan)
# ⚠️ Ordre des middlewares = ordre d’ajout.
# Mets la limite de taille tôt, avant (ou à côté de) CORS/GZip/etc.
app.add_middleware(
    MaxBodySizeMiddleware,
    max_body_size=settings.max_upload_bytes,
)

# Inclusion des routes (comme avant)
for r in routers:
    app.include_router(r)
