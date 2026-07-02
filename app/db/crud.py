from sqlalchemy.orm import Session

from app.db.models import Booking, Document


def save_document_metadata(
    db: Session,
    filename: str,
    file_type: str,
    chunk_strategy: str,
    total_chunks: int,
) -> Document:
    """Persist document metadata after successful ingestion."""
    doc = Document(
        filename=filename,
        file_type=file_type,
        chunk_strategy=chunk_strategy,
        total_chunks=total_chunks,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def save_booking(
    db: Session,
    session_id: str,
    name: str,
    email: str,
    date: str,
    time: str,
) -> Booking:
    """Persist an interview booking extracted by the LLM."""
    booking = Booking(
        session_id=session_id,
        name=name,
        email=email,
        date=date,
        time=time,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


def get_all_bookings(db: Session) -> list[Booking]:
    """Return all interview bookings from the database."""
    return db.query(Booking).all()


def clear_bookings_by_session_id(db: Session, session_id: str) -> int:
    """Delete interview bookings for a specific session from the database."""
    deleted_count = (
        db.query(Booking).filter(Booking.session_id == session_id).delete(synchronize_session=False)
    )
    db.commit()
    return deleted_count
