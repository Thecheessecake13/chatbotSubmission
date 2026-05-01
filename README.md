# Smart Document Q&A System

A production-oriented FastAPI service where users upload PDF/DOCX documents and ask natural-language questions answered from retrieved document context.

## Live Deployment

The API is deployed on Railway.

- Base URL: `https://chatbotsubmission-production-eabb.up.railway.app`
- Landing page: `https://chatbotsubmission-production-eabb.up.railway.app/`
- Health check: `https://chatbotsubmission-production-eabb.up.railway.app/api/v1/health`
- API docs: `https://chatbotsubmission-production-eabb.up.railway.app/docs`

### Live API Test

Health check:

```bash
curl "https://chatbotsubmission-production-eabb.up.railway.app/api/v1/health"
```

Expected response:

```json
{"status":"ok"}
```

Upload a sample document:

```bash
curl -X POST "https://chatbotsubmission-production-eabb.up.railway.app/api/v1/documents" \
  -F "file=@sample_docs/acme_leave_policy.pdf"
```

Check document status:

```bash
curl "https://chatbotsubmission-production-eabb.up.railway.app/api/v1/documents/<document_id>"
```

Ask a question after the document status becomes `ready`:

```bash
curl -X POST "https://chatbotsubmission-production-eabb.up.railway.app/api/v1/documents/<document_id>/ask" \
  -H "Content-Type: application/json" \
  -d '{"question":"How many vacation days do full-time employees receive?"}'
```

### Railway Deployment Notes

The Railway deployment runs the FastAPI API and Celery worker from the same service so uploaded files and FAISS indexes are available to both processes during live demo testing. PostgreSQL and Redis are managed Railway services.

Required Railway variables include:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Railway PostgreSQL connection URL using `postgresql+psycopg://...` |
| `REDIS_URL` | Railway Redis URL |
| `CELERY_BROKER_URL` | Redis URL used by Celery |
| `CELERY_RESULT_BACKEND` | Redis URL used for Celery results |
| `OLLAMA_BASE_URL` | Ollama service URL |
| `OLLAMA_MODEL` | Model used for answer generation |
| `EMBEDDING_MODEL` | Sentence Transformers embedding model |
| `UPLOAD_DIR` | Upload directory |
| `FAISS_DIR` | FAISS index directory |

## What Is Included

- FastAPI REST API with OpenAPI docs at `/docs`
- Async document processing with Celery + Redis
- PostgreSQL persistence with SQLAlchemy + Alembic
- PDF/DOCX text extraction
- Overlapping text chunking designed for retrieval quality
- Sentence Transformers embeddings
- Per-document FAISS vector indexes
- Ollama answer generation with a strict grounded-answer prompt
- Conversation memory for follow-up questions
- Processing progress and failure states
- Docker Compose setup for API, worker, Redis, Postgres, and Ollama
- Three sample documents in `sample_docs/`

## Local Setup

You need Docker and Docker Compose.

```bash
docker compose up --build
```

The first run downloads the configured Ollama model, which can take several minutes depending on the model size and network speed.

The API will be available at:

- Landing page: `http://localhost:8000/`
- API: `http://localhost:8000/api/v1`
- Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`

`docker compose up` starts Postgres, Redis, Ollama, pulls the configured Ollama model, starts the API, runs Alembic migrations, and starts the Celery worker. No database or API-key setup is required for local LLM answers.

## Environment Variables

See `.env.example` for the full list. The most important variables are:

| Variable | Purpose |
| --- | --- |
| `OLLAMA_BASE_URL` | Ollama server URL used for final LLM answers |
| `OLLAMA_MODEL` | Local Ollama model used for answers |
| `EMBEDDING_MODEL` | Sentence Transformers model |
| `DATABASE_URL` | SQLAlchemy database connection |
| `CELERY_BROKER_URL` | Redis broker for Celery |
| `CELERY_RESULT_BACKEND` | Redis backend for Celery task results |
| `FAISS_DIR` | Persistent FAISS index directory |
| `UPLOAD_DIR` | Persistent uploaded-file directory |
| `TOP_K` | Number of chunks retrieved for each answer |
| `MIN_RETRIEVAL_SCORE` | Minimum cosine-similarity score required before context is sent to the LLM |

## Sample API Calls

### 1. Root Status

```bash
curl "http://localhost:8000/"
```

Expected response:

```json
{
  "status": "success",
  "message": "Smart Document Q&A API is running successfully.",
  "docs": "/docs",
  "health": "/api/v1/health"
}
```

### 2. Health Check

```bash
curl "http://localhost:8000/api/v1/health"
```

Expected response:

```json
{"status":"ok"}
```

### 3. Upload a Document

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

### 4. Check Processing Status

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

### 5. Ask a Question

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

### 6. Ask a Follow-Up Question

```bash
curl -X POST "http://localhost:8000/api/v1/documents/<document_id>/ask" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"<conversation_id>","question":"Does any of it carry over?"}'
```

### 7. Read Conversation Messages

```bash
curl "http://localhost:8000/api/v1/conversations/<conversation_id>/messages"
```

## API Overview

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Landing/status message |
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/documents` | Upload PDF/DOCX and enqueue processing |
| `GET` | `/api/v1/documents` | List uploaded documents |
| `GET` | `/api/v1/documents/{document_id}` | Check status/progress |
| `POST` | `/api/v1/documents/{document_id}/ask` | Ask a question |
| `GET` | `/api/v1/documents/{document_id}/conversations` | List conversations for a document |
| `GET` | `/api/v1/conversations/{conversation_id}/messages` | Read conversation messages |

## Design Decisions

### Retrieval Quality

The system chunks extracted text into overlapping windows. Overlap keeps context around boundaries so answers are less likely to miss details split across chunks. PDF chunks retain page numbers, and every answer returns citations with chunk index, page number, similarity score, and a text preview.

Embeddings are normalized and stored in a per-document FAISS `IndexFlatIP`, which makes inner product equivalent to cosine similarity. Search results below `MIN_RETRIEVAL_SCORE` are discarded, so unrelated questions produce a grounded "not enough information" answer instead of sending weak context to the LLM. Per-document indexes keep retrieval simple, predictable, and isolated between users/documents.

For a multi-tenant production system, I would add tenant IDs, object storage, and index compaction/rebuild jobs.

### LLM Grounding

The LLM prompt explicitly says to answer only from retrieved context and to say when the document does not contain enough information.

For follow-up questions, recent conversation turns are used to build the retrieval query before FAISS search, which helps short questions like "Does it carry over?" retrieve the same topic as the previous turn. Conversation history is not treated as evidence unless the retrieved document context supports it.

### Async Design

Upload returns quickly after saving the file and creating a database row. CPU/IO-heavy parsing, chunking, embedding, and FAISS indexing happen in a Celery worker.

Clients can poll `GET /documents/{id}` for:

- `status`
- `progress`
- `chunk_count`
- `error_message`

### Failure Handling

- Unsupported file type: `400 Bad Request`
- Oversized upload: `413 Payload Too Large`
- Asking before processing completes: `409 Conflict`
- Corrupt PDF/DOCX: document status becomes `failed`
- Scanned PDF with no text: document status becomes `failed` with an OCR-related message
- Redis/Celery enqueue failure after upload: document status becomes `failed` and the API returns `503`
- No confident retrieval match: the API returns a grounded "not enough information" answer without calling the LLM
- Missing Ollama configuration: retrieval succeeds, but the answer explains that the LLM is not configured
- Temporary Ollama failure: retried with exponential backoff before returning a graceful message

### Code Structure

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

### Deployment Architecture

Local development uses Docker Compose with separate containers for API, worker, Redis, Postgres, and Ollama.

For the Railway live demo, the API and Celery worker run from the same application service. This keeps uploaded files and FAISS indexes available to both processes during testing. PostgreSQL and Redis run as Railway-managed services.

For a larger production deployment, I would separate the API and worker into independent services and move uploaded files/FAISS indexes to shared object storage or a managed vector database. I would also add authentication, tenant isolation, rate limits, structured logging, and persistent shared storage.

## Tests

```bash
python -m pytest -q
```

The included unit tests cover follow-up-aware retrieval query construction and the no-confident-context path that avoids unnecessary LLM calls.

## Testing the Sample Documents

```bash
curl -X POST "http://localhost:8000/api/v1/documents" -F "file=@sample_docs/vendor_contract_summary.pdf"
curl -X POST "http://localhost:8000/api/v1/documents" -F "file=@sample_docs/candidate_interview_guide.docx"
```

Useful sample questions:

- `How many vacation days do full-time employees receive?`
- `What is the uptime SLA?`
- `What are the interview stages?`
- `When should final decisions be documented?`

## Notes and Limitations

- OCR is not included. Scanned PDFs fail clearly instead of silently producing bad answers.
- FAISS indexes are local files. For horizontal scaling, use shared storage or move to a managed vector database.
- Authentication is intentionally omitted because it was not requested. A production deployment should add auth, tenant isolation, rate limits, and audit logs.
