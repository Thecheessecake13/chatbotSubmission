import json
from collections.abc import Sequence

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.models import Message, MessageRole
from app.services.vector_store import SearchHit


class LLMUnavailableError(Exception):
    pass


def build_context(hits: Sequence[SearchHit]) -> str:
    blocks = []
    for idx, hit in enumerate(hits, start=1):
        page = f'page {hit.chunk.page_number}' if hit.chunk.page_number else 'document'
        blocks.append(f'[source {idx} | chunk {hit.chunk.chunk_index} | {page}]\n{hit.chunk.text}')
    return '\n\n'.join(blocks)


def build_messages(question: str, hits: Sequence[SearchHit], history: Sequence[Message]) -> list[dict[str, str]]:
    system = (
        'You are a careful document Q&A assistant for a B2B SaaS API. '
        'Answer only using the provided document context. '
        'If the answer is not in the context, say that the document does not provide enough information. '
        'Do not invent facts. Keep answers concise, specific, and cite source numbers like [source 1]. '
        'Use conversation history only to resolve follow-up references; never use it as evidence unless it is backed by context.'
    )
    context = build_context(hits)
    messages = [{'role': 'system', 'content': system}]
    if history:
        messages.append({'role': 'system', 'content': 'Recent conversation history for reference:'})
        for item in history[-8:]:
            role = 'assistant' if item.role == MessageRole.assistant else 'user'
            messages.append({'role': role, 'content': item.content[:1800]})
    messages.append({'role': 'user', 'content': f'Document context:\n{context}\n\nQuestion: {question}'})
    return messages


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), retry=retry_if_exception_type(httpx.HTTPError))
def answer_question(question: str, hits: Sequence[SearchHit], history: Sequence[Message]) -> str:
    settings = get_settings()
    if not settings.ollama_base_url.strip() or not settings.ollama_model.strip():
        raise LLMUnavailableError('Ollama is not configured.')

    payload = {
        'model': settings.ollama_model,
        'messages': build_messages(question, hits, history),
        'stream': False,
        'options': {'temperature': 0.1},
    }
    with httpx.Client(base_url=settings.ollama_base_url.rstrip('/'), timeout=120) as client:
        response = client.post('/api/chat', json=payload)
        response.raise_for_status()
    data = response.json()
    return data.get('message', {}).get('content', '') or ''


def citations_json(hits: Sequence[SearchHit]) -> str:
    return json.dumps([
        {
            'chunk_id': str(hit.chunk.id),
            'chunk_index': hit.chunk.chunk_index,
            'page_number': hit.chunk.page_number,
            'score': hit.score,
            'preview': hit.chunk.text[:260],
        }
        for hit in hits
    ])
