from contextlib import asynccontextmanager

from fastapi import FastAPI

import backend.models.analysis  # noqa: F401  (registers the tables)
import backend.models.document  # noqa: F401
import backend.models.document_page  # noqa: F401
from ai_engine.llm.ollama_client import check_ollama
from backend.api.analysis import router as analysis_router
from backend.api.documents import router as documents_router
from backend.core.config import settings
from backend.services.pipeline import recover_interrupted
from database.connection import Base, engine
from backend.api.stats import router as stats_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # temporary, replaced by Alembic later
    recover_interrupted()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(documents_router)
app.include_router(analysis_router)
app.include_router(stats_router)

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