# backend/app/api/routes/base.py

from fastapi import APIRouter

router = APIRouter()

@router.get("/ping", tags=["Health"])
def ping():
    return {"status": "ok", "message": "pong"}
