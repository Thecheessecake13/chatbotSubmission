import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.domain import DocumentStatus, MessageRole


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    status: DocumentStatus
    progress: int
    error_message: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class UploadResponse(BaseModel):
    document: DocumentOut
    status_url: str


class ConversationOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class Citation(BaseModel):
    chunk_id: uuid.UUID
    chunk_index: int
    page_number: int | None = None
    score: float
    preview: str


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    conversation_id: uuid.UUID | None = None
    top_k: int | None = Field(default=None, ge=1, le=12)


class AskResponse(BaseModel):
    document_id: uuid.UUID
    conversation_id: uuid.UUID
    answer: str
    citations: list[Citation]


class MessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime

    model_config = {'from_attributes': True}


class HealthResponse(BaseModel):
    status: str
