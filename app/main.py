from fastapi import FastAPI
from app.core.config import settings
from app.core.middleware import setup_cors
from app.api.v1.router import api_router
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
)

setup_cors(app)

app.include_router(api_router, prefix="/api/v1", tags=["KYC"])

# Route de santé
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "KYC Validation Pipeline",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
