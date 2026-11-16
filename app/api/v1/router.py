"""
Routeur principal de l'API v1.

Agrège les routeurs de chaque domaine fonctionnel (``endpoints/*``). Pour
ajouter une ressource, créer un module dans ``endpoints/`` et l'inclure ici.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import kyc

api_router = APIRouter()
api_router.include_router(kyc.router)
