# Smart Document Q&A System

A production-oriented FastAPI service where users upload PDF/DOCX documents and ask natural-language questions answered from retrieved document context.

## What is included

- FastAPI REST API with OpenAPI docs at `/docs`
- Async document processing with Celery + Redis
- PostgreSQL persistence with SQLAlchemy + Alembic
- PDF/DOCX text extraction
- Overlapping text chunking designed for retrieval quality
- Sentence Transformers embeddings
- Per-document FAISS vector indexes
- OpenAI answer generation with a strict grounded-answer prompt
- Conversation memory for follow-up questions
- Processing progress and failure states
- Docker Compose setup for API, worker, Redis, and Postgres
- Three sample documents in `sample_docs/`

## Local setup

You need Docker and Docker Compose.

```bash
# Optional but required for LLM answers. Retrieval still works without it.
export OPENAI_API_KEY="sk-..."

docker compose up --build
```

The API will be available at:

- API: `http://localhost:8000/api/v1`
- Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`

`docker compose up` starts Postgres, Redis, the API, runs Alembic migrations, and starts the Celery worker. No database setup is required.

## Environment variables

See `.env.example` for the full list. The most important variables are:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Enables final LLM answers |
| `OPENAI_MODEL` | Chat model used for answers |
| `EMBEDDING_MODEL` | Sentence Transformers model |
| `DATABASE_URL` | SQLAlchemy database connection |
| `CELERY_BROKER_URL` | Redis broker for Celery |
| `FAISS_DIR` | Persistent FAISS index directory |
| `UPLOAD_DIR` | Persistent uploaded-file directory |
| `TOP_K` | Number of chunks retrieved for each answer |
| `MIN_RETRIEVAL_SCORE` | Minimum cosine-similarity score required before context is sent to the LLM |

## Sample API calls

### 1. Upload a document

```bash
curl -X POST "http://localhost:8000/api/v1/documents" \
  -F "file=@sample_docs/acme_leave_policy.pdf"
```

Response:

```json
{
  "document": {
    "id": "<document_id>",
    "filename": "acme_leave_policy.pdf",
    "status": "uploaded",
    "progress": 0,
    "chunk_count": 0
  },
  "status_url": "/documents/<document_id>"
}
```

### 2. Check processing status

```bash
curl "http://localhost:8000/api/v1/documents/<document_id>"
```

Wait until the document status is `ready`.

```json
{
  "id": "<document_id>",
  "status": "ready",
  "progress": 100,
  "chunk_count": 3
}
```

If a document is corrupt or unsupported, status becomes `failed` and `error_message` explains why.

### 3. Ask a question

```bash
curl -X POST "http://localhost:8000/api/v1/documents/<document_id>/ask" \
  -H "Content-Type: application/json" \
  -d '{"question":"How many vacation days do full-time employees receive?"}'
```

Response includes the answer, conversation ID, and citations back to chunks.

```json
{
  "document_id": "<document_id>",
  "conversation_id": "<conversation_id>",
  "answer": "Full-time employees receive 20 paid vacation days per calendar year [source 1].",
  "citations": [
    {
      "chunk_id": "...",
      "chunk_index": 0,
      "page_number": 1,
      "score": 0.72,
      "preview": "Acme Corp Leave Policy Full-time employees receive..."
    }
  ]
}
```

### 4. Ask a follow-up question

```bash
curl -X POST "http://localhost:8000/api/v1/documents/<document_id>/ask" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"<conversation_id>","question":"Does any of it carry over?"}'
```

### 5. Read conversation messages

```bash
curl "http://localhost:8000/api/v1/conversations/<conversation_id>/messages"
```

## API overview

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/documents` | Upload PDF/DOCX and enqueue processing |
| `GET` | `/api/v1/documents` | List uploaded documents |
| `GET` | `/api/v1/documents/{document_id}` | Check status/progress |
| `POST` | `/api/v1/documents/{document_id}/ask` | Ask a question |
| `GET` | `/api/v1/documents/{document_id}/conversations` | List conversations for a document |
| `GET` | `/api/v1/conversations/{conversation_id}/messages` | Read conversation messages |

## Design decisions

### Retrieval quality

The system chunks extracted text into overlapping windows. Overlap keeps context around boundaries so answers are less likely to miss details split across chunks. PDF chunks retain page numbers, and every answer returns citations with chunk index, page number, similarity score, and a text preview.

Embeddings are normalized and stored in a per-document FAISS `IndexFlatIP`, which makes inner product equivalent to cosine similarity. Search results below `MIN_RETRIEVAL_SCORE` are discarded, so unrelated questions produce a grounded "not enough information" answer instead of sending weak context to the LLM. Per-document indexes keep retrieval simple, predictable, and isolated between users/documents. For a multi-tenant production system, I would add tenant IDs, object storage, and index compaction/rebuild jobs.

### LLM grounding

The LLM prompt explicitly says to answer only from retrieved context and to say when the document does not contain enough information. For follow-up questions, recent conversation turns are used to build the retrieval query before FAISS search, which helps short questions like "Does it carry over?" retrieve the same topic as the previous turn. Conversation history is not treated as evidence unless the retrieved document context supports it.

### Async design

Upload returns `202 Accepted` quickly after saving the file and creating a database row. CPU/IO-heavy parsing, chunking, embedding, and FAISS indexing happen in a Celery worker. Clients can poll `GET /documents/{id}` for `status`, `progress`, `chunk_count`, and `error_message`.

### Failure handling

- Unsupported file type: `400 Bad Request`
- Oversized upload: `413 Payload Too Large`
- Asking before processing completes: `409 Conflict`
- Corrupt PDF/DOCX: document status becomes `failed`
- Scanned PDF with no text: document status becomes `failed` with an OCR-related message
- Redis/Celery enqueue failure after upload: document status becomes `failed` and the API returns `503`
- No confident retrieval match: the API returns a grounded "not enough information" answer without calling the LLM
- Missing OpenAI key: retrieval succeeds, but the answer explains that the LLM is not configured
- Temporary OpenAI failure: retried with exponential backoff before returning a graceful message

### Code structure

The code is split by responsibility:

```text
app/api/          HTTP routes
app/core/         configuration
app/db/           SQLAlchemy engine/session
app/models/       database models
app/schemas/      request/response schemas
app/services/     extraction, chunking, embeddings, FAISS, LLM, Q&A orchestration
app/tasks/        Celery tasks
alembic/          migrations
sample_docs/      immediate test files
```

### Deployment

This repo is containerized and can be deployed to a VM, Render, Railway, Fly.io, or ECS. A simple deployment path is:

1. Push the repo to GitHub.
2. Create managed Postgres and Redis.
3. Deploy two services from the same image:
   - API command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Worker command: `celery -A app.worker.celery_app worker --loglevel=INFO`
4. Set environment variables from `.env.example`.
5. Attach persistent volumes or object storage for `UPLOAD_DIR` and `FAISS_DIR`.

Deployment link for submission: not configured in this local workspace. Before final submission, deploy the API and worker with the commands above and replace this line with the hosted base URL, for example `https://your-document-qa-api.example.com/api/v1`.

## Tests

```bash
python -m pytest -q
```

The included unit tests cover follow-up-aware retrieval query construction and the no-confident-context path that avoids unnecessary LLM calls.

## Testing the sample documents

```bash
curl -X POST "http://localhost:8000/api/v1/documents" -F "file=@sample_docs/vendor_contract_summary.pdf"
curl -X POST "http://localhost:8000/api/v1/documents" -F "file=@sample_docs/candidate_interview_guide.docx"
```

Useful sample questions:

- `How many vacation days do full-time employees receive?`
- `What is the uptime SLA?`
- `What are the interview stages?`
- `When should final decisions be documented?`

## Notes and limitations

- OCR is not included. Scanned PDFs fail clearly instead of silently producing bad answers.
- FAISS indexes are local files. For horizontal scaling, use shared storage or move to a managed vector database.
- Authentication is intentionally omitted because it was not requested; production deployment should add auth, tenant isolation, rate limits, and audit logs.
