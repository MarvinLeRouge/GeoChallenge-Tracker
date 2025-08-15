# backend/app/main.py

import os
from fastapi import FastAPI
from app.api.routes import routers
from app.db.seed_indexes import ensure_indexes
from app.db.seed_data import seed_referentials

app = FastAPI(title="GeoChallenge API")

@app.on_event("startup")
def _startup():
    ensure_indexes()  # toujours

    if os.getenv("SEED_ON_STARTUP", "false").lower() == "true":
        seed_referentials()  # idempotent et léger uniquement

# Inclusion des routes
for r in routers:
    app.include_router(r)
