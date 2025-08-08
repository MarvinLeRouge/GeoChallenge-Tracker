# backend/app/api/routes/__init__.py
 
from .base import router as base_router
from .auth import router as auth_router

routers = [base_router, auth_router]