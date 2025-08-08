# backend/app/main.py

from fastapi import FastAPI
from app.api.routes import routers

app = FastAPI(title="GeoChallenge API")

# Inclusion des routes
for r in routers:
    app.include_router(r)
