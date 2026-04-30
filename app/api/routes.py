import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Conversation, Document, DocumentStatus
from app.schemas.api import AskRequest, AskResponse, ConversationOut, DocumentOut, HealthResponse, MessageOut, UploadResponse
from app.services.conversation import ConversationDocumentMismatchError, DocumentNotReadyError, ask_document
from app.tasks.document_tasks import process_document

router = APIRouter()


def _safe_filename(filename: str) -> str:
    return Path(filename).name.replace(' ', '_')


@router.get('/health', response_model=HealthResponse, tags=['system'])
def health() -> HealthResponse:
    return HealthResponse(status='ok')


@router.post('/documents', response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED, tags=['documents'])
def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)) -> UploadResponse:
    settings = get_settings()
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in {'.pdf', '.docx'}:
        raise HTTPException(status_code=400, detail='Only PDF and DOCX uploads are supported.')

    doc_id = uuid.uuid4()
    target = settings.upload_dir / f'{doc_id}_{_safe_filename(file.filename or "document")}'

    bytes_written = 0
    with target.open('wb') as out:
        while chunk := file.file.read(1024 * 1024):
            bytes_written += len(chunk)
            if bytes_written > settings.max_upload_bytes:
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f'Max upload size is {settings.max_upload_mb} MB.')
            out.write(chunk)

    document = Document(
        id=doc_id,
        filename=file.filename or target.name,
        content_type=file.content_type or 'application/octet-stream',
        storage_path=str(target),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    try:
        process_document.delay(str(document.id))
    except Exception as exc:
        document.status = DocumentStatus.failed
        document.progress = 100
        document.error_message = 'Document was uploaded, but processing could not be queued. Please retry later.'
        db.commit()
        raise HTTPException(status_code=503, detail=document.error_message) from exc
    return UploadResponse(document=document, status_url=f'/documents/{document.id}')


@router.get('/documents', response_model=list[DocumentOut], tags=['documents'])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentOut]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())).all())


@router.get('/documents/{document_id}', response_model=DocumentOut, tags=['documents'])
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> DocumentOut:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail='Document not found.')
    return document


@router.post('/documents/{document_id}/ask', response_model=AskResponse, tags=['qa'])
def ask(document_id: uuid.UUID, payload: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail='Document not found.')
    try:
        return ask_document(db, document, payload.question, payload.conversation_id, payload.top_k)
    except DocumentNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ConversationDocumentMismatchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get('/documents/{document_id}/conversations', response_model=list[ConversationOut], tags=['conversations'])
def list_conversations(document_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ConversationOut]:
    return list(db.scalars(select(Conversation).where(Conversation.document_id == document_id).order_by(Conversation.updated_at.desc())).all())


@router.get('/conversations/{conversation_id}/messages', response_model=list[MessageOut], tags=['conversations'])
def list_messages(conversation_id: uuid.UUID, db: Session = Depends(get_db)) -> list[MessageOut]:
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail='Conversation not found.')
    result: list[MessageOut] = []
    for message in conversation.messages:
        citations = [] if not message.citations_json else json.loads(message.citations_json)
        result.append(MessageOut.model_validate(message).model_copy(update={'citations': citations}))
    return result
