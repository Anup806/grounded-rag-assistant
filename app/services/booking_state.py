import json

import redis

from app.core.config import settings

# Lazy-loaded singleton — separate from memory.py's chat history client
# so booking state and conversation history stay logically distinct,
# even though they share the same Redis instance.
_redis: redis.Redis | None = None

# TTL for an in-progress booking: 1 hour. If the user abandons a partial
# booking, it expires instead of lingering forever.
PENDING_TTL_SECONDS = 3_600


def _get_redis() -> redis.Redis:
    """Return a shared Redis client instance."""
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def _key(session_id: str) -> str:
    """Build the Redis key for a session's in-progress booking."""
    return f"booking_pending:{session_id}"


def get_pending_booking(session_id: str) -> dict[str, str | None]:
    """
    Retrieve the partially-filled booking slots for a session.

    Returns:
        Dict with keys name/email/date/time, values are str or None.
        Returns all-None dict if no pending booking exists.
    """
    raw = _get_redis().get(_key(session_id))
    if raw:
        return json.loads(raw)
    return {"name": None, "email": None, "date": None, "time": None}


def save_pending_booking(session_id: str, state: dict[str, str | None]) -> None:
    """Persist the current (possibly still incomplete) booking slots."""
    _get_redis().set(_key(session_id), json.dumps(state), ex=PENDING_TTL_SECONDS)


def clear_pending_booking(session_id: str) -> None:
    """Delete in-progress booking slots — call after a booking completes."""
    _get_redis().delete(_key(session_id))