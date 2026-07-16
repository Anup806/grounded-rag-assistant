import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from qdrant_client.http.exceptions import ResponseHandlingException

from app.api import conversation, ingestion
from app.db.database import create_tables
from app.services.vector_store import ensure_collection

from fastapi.middleware.cors import CORSMiddleware  

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Run startup tasks before the server begins accepting requests:
    - Create SQLite tables (idempotent)
    - Ensure Qdrant collection exists (idempotent)
    """
    create_tables()
    try:
        ensure_collection()
    except ResponseHandlingException as exc:
        logger.warning("Skipping Qdrant collection initialization during startup: %s", exc)
    yield
    # No teardown needed


app = FastAPI(
    title="Backend RAG",
    description=(
        "Two-API backend for document ingestion and conversational RAG "
        "with Redis-backed multi-turn memory and LLM-powered interview booking."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion.router)
app.include_router(conversation.router)


@app.get("/", tags=["Health"])
async def root() -> dict:
    """Health check endpoint."""
    return {
        "status": "running",
        "docs": "/docs",
        "apis": ["/ingest/upload", "/chat/message"],
    }
