from fastapi import FastAPI

from backend.core.config import settings
from ai_engine.llm.ollama_client import check_ollama

from backend.api.documents import router as documents_router

app = FastAPI(title=settings.app_name)
app.include_router(documents_router)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
    }

@app.get("/health/ollama")
def health_ollama():
    return check_ollama()