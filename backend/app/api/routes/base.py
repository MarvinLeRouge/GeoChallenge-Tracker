from fastapi import APIRouter

router = APIRouter()

@router.get("/ping", tags=["Health"])
def ping():
    return {"status": "ok", "message": "pong"}
