import uuid

from fastapi import APIRouter, Depends, HTTPException
from qdrant_client.http.exceptions import ResponseHandlingException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.crud import clear_bookings_by_session_id, get_all_bookings, save_booking
from app.db.database import get_db
from app.services.booking import detect_booking
from app.services.memory import append_to_history, clear_history, get_chat_history
from app.services.rag import generate_rag_response

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

    # Load history once — needed by booking detection to merge fields given
    # across multiple turns, and reused below for the RAG branch.
    existing_history: list[dict[str, str]] = get_chat_history(session_id)

    # ── Booking detection first ──────────────────────────────────────────────
    booking_result: dict = detect_booking(request.message, chat_history=existing_history)
    booking_confirmed: dict | None = None

    if booking_result.get("booking") is True:
        # All fields present — save and confirm
        booking = save_booking(
            db=db,
            session_id=session_id,
            name=booking_result["name"],
            email=booking_result["email"],
            date=booking_result["date"],
            time=booking_result["time"],
        )
        response_text = (
            f"Interview booked successfully!\n"
            f"Name:  {booking_result['name']}\n"
            f"Email: {booking_result['email']}\n"
            f"Date:  {booking_result['date']}\n"
            f"Time:  {booking_result['time']}\n"
            f"Booking ID: {booking.id}"
        )
        booking_confirmed = {
            "id": booking.id,
            **{k: booking_result[k] for k in ("name", "email", "date", "time")},
        }

    elif booking_result.get("booking") is False:
        # Partial booking — prompt for missing fields
        missing: list[str] = booking_result.get("missing", [])
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

    # Persist this turn to Redis
    append_to_history(session_id, request.message, response_text)

    return {
        "session_id": session_id,
        "response": response_text,
        "booking": booking_confirmed,
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
