# Backend RAG with Two RESTAPI 

A backend system with two REST APIs built using FastAPI:
1. **Document Ingestion API** — upload PDF/TXT files, chunk, embed, and store in Qdrant
2. **Conversational RAG API** — multi-turn Q&A over uploaded documents with Redis memory and LLM-powered interview booking

---

## Tech Stack

| Component        | Tool                              |
|------------------|-----------------------------------|
| Web framework    | FastAPI + Uvicorn                 |
| Vector database  | Qdrant (Docker)                   |
| Chat memory      | Redis (Docker)                    |
| Metadata DB      | SQLite via SQLAlchemy             |
| Embeddings       | sentence-transformers (local CPU) |
| LLM              | Groq API (llama-3.1-8b-instant)   |
| PDF parsing      | PyMuPDF                           |
| Sentence chunking| NLTK                              |

---

## Prerequisites

- Python 3.11+
- Docker Desktop (for Qdrant + Redis)
- A free Groq API key from [console.groq.com](https://console.groq.com)

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Anup806/Backend-RAG-with-Two-RESTAPI
cd Backend-RAG-with-Two-RESTAPI
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
copy .env.example .env
```

Open `.env` and add your Groq API key:

```
GROQ_API_KEY=your_actual_groq_api_key_here
```

Leave all other values as their defaults unless you have a reason to change them.

### 5. Start Qdrant and Redis via Docker

```bash
docker compose up -d
```

Verify both containers are running:

```bash
docker ps
```

You should see `backend_qdrant` and `backend_redis` both with status `Up`.

---

## Running the Server

```bash
uvicorn app.main:app --reload
```

The server starts at `http://localhost:8000`.

Interactive API docs: `http://localhost:8000/docs`

---

## API Reference

### Document Ingestion API

#### `POST /ingest/upload`

Upload a PDF or TXT file and ingest it into the RAG system.

**Form fields:**
| Field    | Type   | Required | Description                          |
|----------|--------|----------|--------------------------------------|
| file     | File   | Yes      | PDF or TXT file                      |
| strategy | String | Yes      | `fixed` or `sentence`                |

**Example (PowerShell):**

```powershell
curl -X POST "http://localhost:8000/ingest/upload" `
  -F "file=@C:\path\to\document.pdf" `
  -F "strategy=sentence"
```

**Example response:**

```json
{
  "message": "Document ingested successfully.",
  "document_id": 1,
  "filename": "document.pdf",
  "strategy_used": "sentence",
  "total_chunks_stored": 42
}
```

---

### Conversational RAG API

#### `POST /chat/message`

Send a message. The system answers from uploaded documents or books an interview.

**Request body:**

```json
{
  "session_id": "optional-existing-session-id",
  "message": "What is the company refund policy?"
}
```

If `session_id` is omitted, a new one is auto-generated and returned in the response.

**Example response (RAG answer):**

```json
{
  "session_id": "abc-123-...",
  "response": "The refund policy states that...",
  "booking": null
}
```

**Example — booking an interview:**

Send this message:
```
I'd like to book an interview. My name is Anup Rai, email is anup@gmail.com, date July 10 2026, time 2pm.
```

Response:
```json
{
  "session_id": "abc-123-...",
  "response": "Interview booked successfully!\nName:  Anup Rai\n...",
  "booking": {
    "id": 1,
    "name": "Anup Rai",
    "email": "anup@gmail.com",
    "date": "2026-07-10",
    "time": "14:00"
  }
}
```

#### `GET /chat/history/{session_id}`

Retrieve full conversation history for a session.

#### `POST /chat/clear`

Clear conversation history for a session.

```json
{ "session_id": "abc-123-..." }
```

#### `GET /chat/bookings`

List all interview bookings stored in the database.

#### `DELETE /chat/bookings/{session_id}`

Delete the interview booking(s) for one specific `session_id` from SQLite.

Example:

```http
DELETE /chat/bookings/abc-123-...
```

---

## Chunking Strategies

| Strategy   | How it works                                              | Best for                     |
|------------|-----------------------------------------------------------|------------------------------|
| `fixed`    | Splits text into 500-character chunks with 50-char overlap| Long uniform text, reports   |
| `sentence` | Groups 5 sentences per chunk using NLTK sentence tokenizer| Articles, conversational text|

---

## Project Structure

```
Backend RAG with Two FastAPI/
├── app/
│   ├── main.py                  # FastAPI app, startup tasks, router registration
│   ├── api/
│   │   ├── ingestion.py         # POST /ingest/upload
│   │   └── conversation.py      # POST /chat/message and related endpoints
│   ├── services/
│   │   ├── extractor.py         # PDF/TXT text extraction (PyMuPDF)
│   │   ├── chunker.py           # Fixed-size and sentence-based chunking
│   │   ├── embedder.py          # sentence-transformers embedding
│   │   ├── vector_store.py      # Qdrant store and search
│   │   ├── memory.py            # Redis chat history manager
│   │   ├── rag.py               # Custom RAG pipeline (no RetrievalQAChain)
│   │   └── booking.py           # LLM-based booking detection and extraction
│   ├── db/
│   │   ├── database.py          # SQLite engine and session factory
│   │   ├── models.py            # Document and Booking table definitions
│   │   └── crud.py              # Read/write functions
│   └── core/
│       └── config.py            # Settings loaded from .env
├── .env.example                 # Template — copy to .env and fill in
├── .gitignore
├── docker-compose.yml           # Qdrant + Redis containers
├── requirements.txt
└── README.md
```

---

## Stopping the Services

```bash
docker compose down
```

To also delete all stored data (Qdrant vectors + Redis sessions):

```bash
docker compose down -v
```
