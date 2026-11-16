"""
Point d'entrée de l'application FastAPI.

Lancement en développement ::

    uvicorn app.main:app --reload
"""
from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import setup_cors

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Construit l'application : logging, middlewares et routes."""
    configure_logging()

    if settings.JWT_SECRET_KEY == "change-me":
        logger.warning("JWT_SECRET_KEY utilise la valeur par défaut : à définir en production.")

    application = FastAPI(title=settings.PROJECT_NAME, version=settings.PROJECT_VERSION)
    setup_cors(application)
    application.include_router(api_router, prefix=settings.API_V1_STR)

    @application.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """Sonde de disponibilité utilisée par Docker et les orchestrateurs."""
        return {
            "status": "healthy",
            "service": settings.PROJECT_NAME,
            "version": settings.PROJECT_VERSION,
        }

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
