from fastapi import FastAPI
from app.api.routes.base import router as base_router

app = FastAPI(title="GeoChallenge API")

# Inclusion des routes
app.include_router(base_router)
