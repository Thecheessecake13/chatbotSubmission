import json
import uuid
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import DocumentChunk
from app.services.embeddings import embed_texts


@dataclass(frozen=True)
class SearchHit:
    chunk: DocumentChunk
    score: float


def _paths(document_id: uuid.UUID) -> tuple[Path, Path]:
    base = get_settings().faiss_dir
    return base / f'{document_id}.index', base / f'{document_id}.meta.json'


def build_index(document_id: uuid.UUID, chunks: list[DocumentChunk]) -> None:
    if not chunks:
        raise ValueError('Cannot build FAISS index without chunks')
    embeddings = embed_texts([chunk.text for chunk in chunks])
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    index_path, meta_path = _paths(document_id)
    faiss.write_index(index, str(index_path))
    meta_path.write_text(json.dumps([str(chunk.id) for chunk in chunks]), encoding='utf-8')


def search(db: Session, document_id: uuid.UUID, query: str, top_k: int, min_score: float | None = None) -> list[SearchHit]:
    index_path, meta_path = _paths(document_id)
    if not index_path.exists() or not meta_path.exists():
        raise FileNotFoundError('Vector index is not available yet')

    index = faiss.read_index(str(index_path))
    ids = [uuid.UUID(item) for item in json.loads(meta_path.read_text(encoding='utf-8'))]
    query_vector = embed_texts([query])
    scores, positions = index.search(np.asarray(query_vector, dtype='float32'), top_k)

    hits: list[SearchHit] = []
    for score, position in zip(scores[0], positions[0], strict=False):
        if position < 0 or position >= len(ids):
            continue
        if min_score is not None and float(score) < min_score:
            continue
        chunk = db.scalar(select(DocumentChunk).where(DocumentChunk.id == ids[position]))
        if chunk:
            hits.append(SearchHit(chunk=chunk, score=float(score)))
    return hits
