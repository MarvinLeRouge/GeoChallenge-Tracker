# backend/app/main.py

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import routers
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware import MaxBodySizeMiddleware
from app.core.settings import get_settings
from app.db.seed_data import seed_referentials
from app.db.seed_indexes import ensure_indexes
from app.services.referentials_cache import populate_mapping

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    await populate_mapping()
    await ensure_indexes()

    if os.getenv("SEED_ON_STARTUP", "false").lower() == "true":
        await seed_referentials()  # idempotent et léger; seed_referentials est async

    yield  # l'app tourne ici

    # --- shutdown ---
    # rien pour le moment


app = FastAPI(title=settings.app_name + " API", version=settings.api_version, lifespan=lifespan)
# ⚠️ Ordre des middlewares = ordre d’ajout.
# Mets la limite de taille tôt, avant (ou à côté de) CORS/GZip/etc.
app.add_middleware(
    MaxBodySizeMiddleware,
    max_body_size=settings.max_upload_bytes,
)

# Enregistrement des gestionnaires d'exceptions globaux
register_exception_handlers(app)

# Inclusion des routes (comme avant)
for r in routers:
    app.include_router(r)
