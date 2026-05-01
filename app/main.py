from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.db import models  # noqa: F401
from app.db.session import Base, engine

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Document upload and conversational Q&A API using FastAPI, Celery, "
        "FAISS, sentence-transformers, and Ollama."
    ),
)


@app.on_event("startup")
def create_database_tables() -> None:
    """
    Ensure Railway/Postgres has the required tables before handling requests.

    Alembic migrations are still included in the project, but this makes the
    deployed demo resilient if Railway startup migrations do not complete.
    """
    Base.metadata.create_all(bind=engine)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
