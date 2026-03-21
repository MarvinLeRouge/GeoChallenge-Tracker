# backend/app/main.py

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import routers
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware import MaxBodySizeMiddleware
from app.core.settings import get_settings
from app.db.mongodb import close_mongodb_connection
from app.db.seed_data import seed_referentials
from app.db.seed_indexes import ensure_indexes
from app.services.referentials_cache import populate_mapping

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    # Skip populate_mapping and ensure_indexes in test mode for faster tests
    # These are already tested separately in unit/integration tests
    if not os.getenv("TEST_MODE", "false").lower() == "true":
        await populate_mapping()
        await ensure_indexes()

        if os.getenv("SEED_ON_STARTUP", "false").lower() == "true":
            await seed_referentials()  # idempotent et léger; seed_referentials est async

    yield  # l'app tourne ici

    # --- shutdown ---
    await close_mongodb_connection()


app = FastAPI(title=settings.app_name + " API", version=settings.api_version, lifespan=lifespan)
# ⚠️ Ordre des middlewares = ordre d’ajout.
# CORS en premier pour que les requêtes OPTIONS (preflight) ne soient pas bloquées.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    MaxBodySizeMiddleware,
    max_body_size=settings.max_upload_bytes,
)

# Enregistrement des gestionnaires d'exceptions globaux
register_exception_handlers(app)

# Inclusion des routes (comme avant)
for r in routers:
    app.include_router(r)
