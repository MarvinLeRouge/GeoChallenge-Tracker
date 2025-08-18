# backend/app/api/routes/__init__.py
 
from .base import router as base_router
from .auth import router as auth_router
from .caches import router as caches_router
from .challenges import router as challenges_router

routers = [
    base_router, 
    auth_router, 
    caches_router, 
    challenges_router
]