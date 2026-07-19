import uuid

from fastapi import APIRouter, Depends, HTTPException
from qdrant_client.http.exceptions import ResponseHandlingException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.crud import clear_bookings_by_session_id, get_all_bookings, save_booking
from app.db.database import get_db
from app.services.booking import extract_booking_fields
from app.services.booking_state import (
    clear_pending_booking,
    get_pending_booking,
    save_pending_booking,
)
from app.services.memory import append_to_history, clear_history, get_chat_history
from app.services.rag import generate_rag_response

_BOOKING_FIELDS: tuple[str, ...] = ("name", "email", "date", "time")

router = APIRouter(prefix="/chat", tags=["Conversational RAG"])


# ── Request / Response schemas ──────────────────────────────────────────────


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class ClearRequest(BaseModel):
    session_id: str


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/message", summary="Send a message to the RAG assistant")
async def chat_message(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Send a message and receive a RAG-powered response.

    Behaviour:
    - If the message contains a complete interview booking request,
      the booking is extracted by the LLM, saved to SQLite, and confirmed.
    - If the booking is incomplete, the user is asked for the missing fields.
    - Otherwise, the custom RAG pipeline retrieves relevant document chunks
      and generates a grounded answer.

    Conversation history is stored in Redis per session_id.
    A new session_id is auto-generated if one is not provided.
    """
    # Auto-generate session_id when not supplied by the caller
    session_id: str = request.session_id or str(uuid.uuid4())

    # ── Booking detection first ──────────────────────────────────────────────
    # The LLM extracts fields from ONLY this message (no history replay —
    # that was causing the model to anchor on its own previous "still need"
    # replies). Python merges the result into whatever was already collected
    # for this session and deterministically checks completeness.
    extracted: dict = extract_booking_fields(request.message)
    pending: dict[str, str | None] = get_pending_booking(session_id)

    has_new_field = any(extracted[f] for f in _BOOKING_FIELDS)
    has_existing_progress = any(pending[f] for f in _BOOKING_FIELDS)

    booking_confirmed: dict | None = None
    # Citations only ever come from an actual RAG lookup — a booking-flow
    # turn (confirmed or still collecting fields) never has document sources.
    sources: list[dict] = []

    if extracted["intent"] or has_new_field:
        # Merge: a newly-extracted field overwrites/fills the pending slot;
        # otherwise keep whatever was already collected.
        merged: dict[str, str | None] = {
            field: extracted[field] or pending[field] for field in _BOOKING_FIELDS
        }
        missing: list[str] = [f for f in _BOOKING_FIELDS if not merged[f]]

        if not missing:
            # All four fields present — save and confirm
            booking = save_booking(
                db=db,
                session_id=session_id,
                name=merged["name"],
                email=merged["email"],
                date=merged["date"],
                time=merged["time"],
            )
            clear_pending_booking(session_id)
            response_text = (
                f"Interview booked successfully!\n"
                f"Name:  {merged['name']}\n"
                f"Email: {merged['email']}\n"
                f"Date:  {merged['date']}\n"
                f"Time:  {merged['time']}\n"
                f"Booking ID: {booking.id}"
            )
            booking_confirmed = {"id": booking.id, **merged}
        else:
            # Still incomplete — persist progress and ask for what's left
            save_pending_booking(session_id, merged)
            response_text = (
                f"To book an interview I still need: {', '.join(missing)}. "
                "Please provide the missing information."
            )

    else:
        # ── Normal RAG query ─────────────────────────────────────────────────
        try:
            rag_result: dict = generate_rag_response(
                user_query=request.message,
                session_id=session_id,
            )
        except ResponseHandlingException as exc:
            raise HTTPException(
                status_code=503,
                detail="Qdrant is unavailable. Start the vector database and try again.",
            ) from exc
        response_text = rag_result["answer"]
        sources = rag_result["sources"]

    # Persist this turn to Redis
    append_to_history(session_id, request.message, response_text)

    return {
        "session_id": session_id,
        "response": response_text,
        "booking": booking_confirmed,
        "sources": sources,
    }


@router.get("/history/{session_id}", summary="Retrieve conversation history")
async def get_history(session_id: str) -> dict:
    """
    Return the full conversation history for a given session.

    Args:
        session_id: The session identifier returned by /chat/message.
    """
    history = get_chat_history(session_id)
    return {
        "session_id": session_id,
        "total_messages": len(history),
        "history": history,
    }


@router.post("/clear", summary="Clear conversation history for a session")
async def clear_session(request: ClearRequest) -> dict:
    """
    Delete all conversation history stored in Redis for a session.

    Args:
        session_id: The session identifier to clear.
    """
    clear_history(request.session_id)
    return {"message": f"Conversation history cleared for session '{request.session_id}'."}


@router.get("/bookings", summary="List all interview bookings")
async def list_bookings(db: Session = Depends(get_db)) -> dict:
    """Return all interview bookings stored in the SQLite database."""
    bookings = get_all_bookings(db)
    return {
        "total": len(bookings),
        "bookings": [
            {
                "id": b.id,
                "session_id": b.session_id,
                "name": b.name,
                "email": b.email,
                "date": b.date,
                "time": b.time,
                "created_at": str(b.created_at),
            }
            for b in bookings
        ],
    }


@router.delete("/bookings/{session_id}", summary="Delete bookings for a session")
async def clear_bookings(session_id: str, db: Session = Depends(get_db)) -> dict:
    """Remove interview bookings stored in SQLite for one session only."""
    deleted_count = clear_bookings_by_session_id(db, session_id)
    return {
        "message": f"Interview bookings for session '{session_id}' were deleted.",
        "session_id": session_id,
        "deleted_count": deleted_count,
    }