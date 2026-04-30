import uuid
from pathlib import Path

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models import Document, DocumentChunk, DocumentStatus
from app.services.chunking import chunk_pages
from app.services.text_extraction import ExtractionError, extract_text
from app.services.vector_store import build_index
from app.worker import celery_app
from app.core.config import get_settings


def _set_status(document: Document, status: DocumentStatus, progress: int, error: str | None = None) -> None:
    document.status = status
    document.progress = progress
    document.error_message = error


@celery_app.task(name='process_document')
def process_document(document_id: str) -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        document = db.get(Document, uuid.UUID(document_id))
        if not document:
            return
        _set_status(document, DocumentStatus.processing, 10)
        db.commit()

        pages = extract_text(Path(document.storage_path))
        document.progress = 35
        db.commit()

        chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            raise ExtractionError('No useful chunks could be created from this document.')

        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        db.flush()
        db_chunks: list[DocumentChunk] = []
        for index, chunk in enumerate(chunks):
            db_chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                text=chunk.text,
                page_number=chunk.page_number,
                token_estimate=chunk.token_estimate,
            )
            db.add(db_chunk)
            db_chunks.append(db_chunk)
        document.chunk_count = len(db_chunks)
        document.progress = 65
        db.commit()

        fresh_chunks = list(db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document.id).order_by(DocumentChunk.chunk_index.asc())).all())
        build_index(document.id, fresh_chunks)
        _set_status(document, DocumentStatus.ready, 100)
        db.commit()
    except Exception as exc:
        db.rollback()
        document = db.get(Document, uuid.UUID(document_id))
        if document:
            _set_status(document, DocumentStatus.failed, 100, str(exc)[:2000])
            db.commit()
    finally:
        db.close()
