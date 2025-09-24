# backend/app/api/routes/base.py
# Routes de base (health check, version de l’API, etc.).

from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/ping",
    tags=["Health"],
    summary="Vérification de santé de l’API",
    description="Retourne un message 'pong' permettant de tester que l’API répond.",
)
def ping():
    """Health-check API.

    Description:
        Route basique permettant de vérifier la disponibilité de l’API.

    Returns:
        dict: Statut et message de réponse.
    """
    return {"status": "ok", "message": "pong"}
