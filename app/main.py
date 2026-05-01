from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.db.session import Base, engine
from app.models import domain  

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
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root() -> dict[str, object]:
    return {
        "status": "success",
        "message": "Smart Document Q&A API is running successfully.",
        "docs": "/docs",
        "health": "/api/v1/health",
        "endpoints": {
            "upload_document": "POST /api/v1/documents",
            "list_documents": "GET /api/v1/documents",
            "get_document_status": "GET /api/v1/documents/{document_id}",
            "ask_question": "POST /api/v1/documents/{document_id}/ask",
        },
    }


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
