import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Conversation, Document, DocumentStatus, Message, MessageRole
from app.schemas.api import AskResponse, Citation
from app.services.llm import LLMUnavailableError, answer_question, citations_json
from app.services.vector_store import search


class DocumentNotReadyError(Exception):
    pass


class ConversationDocumentMismatchError(Exception):
    pass


def build_retrieval_query(question: str, history: list[Message]) -> str:
    if not history:
        return question

    recent_user_questions = [message.content for message in history if message.role == MessageRole.user][-3:]
    recent_assistant_answers = [message.content for message in history if message.role == MessageRole.assistant][-1:]
    parts = [*recent_user_questions, *recent_assistant_answers, question]
    return '\n'.join(part[:1200] for part in parts if part.strip())


def _no_context_answer() -> str:
    return 'The document does not provide enough information to answer that question.'


def ask_document(db: Session, document: Document, question: str, conversation_id: uuid.UUID | None, top_k: int | None) -> AskResponse:
    if document.status != DocumentStatus.ready:
        raise DocumentNotReadyError(f'Document is {document.status.value}; wait until processing is ready.')

    conversation: Conversation | None = None
    if conversation_id:
        conversation = db.get(Conversation, conversation_id)
        if not conversation or conversation.document_id != document.id:
            raise ConversationDocumentMismatchError('Conversation does not exist for this document.')
    if not conversation:
        conversation = Conversation(document_id=document.id, title=question[:120])
        db.add(conversation)
        db.flush()

    history = list(db.scalars(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.asc())).all())
    settings = get_settings()
    retrieval_query = build_retrieval_query(question, history)
    hits = search(db, document.id, retrieval_query, top_k or settings.top_k, settings.min_retrieval_score)

    user_msg = Message(conversation_id=conversation.id, role=MessageRole.user, content=question)
    db.add(user_msg)
    db.flush()

    if not hits:
        answer = _no_context_answer()
    else:
        try:
            answer = answer_question(question, hits, history)
        except LLMUnavailableError:
            answer = 'The document retrieval succeeded, but Ollama is not configured. Set OLLAMA_BASE_URL and OLLAMA_MODEL to generate final answers.'
        except Exception:
            answer = 'The document retrieval succeeded, but Ollama is currently unavailable. Please retry later.'

    assistant_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.assistant,
        content=answer,
        citations_json=citations_json(hits),
    )
    db.add(assistant_msg)
    db.commit()

    citations = [Citation(**item) for item in json.loads(assistant_msg.citations_json or '[]')]
    return AskResponse(document_id=document.id, conversation_id=conversation.id, answer=answer, citations=citations)
