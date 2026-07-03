import json
import re

from groq import Groq

from app.core.config import settings

_groq_client: Groq | None = None

# NOTE: this prompt deliberately does NOT see conversation history, and does
# NOT try to decide "is the booking complete" — it only extracts whatever
# fields are explicitly present in the single message it is given. State
# accumulation and completeness checks are handled deterministically in
# Python (see app/services/booking_state.py + conversation.py), not by the
# LLM. This avoids the model anchoring on its own previous replies when
# history is replayed back into its context turn after turn.
_EXTRACTION_SYSTEM_PROMPT = """You are a slot-extraction assistant for interview booking. \
Look ONLY at the message you are given — you have no memory of earlier messages, that is \
handled elsewhere. Extract any of these four fields if explicitly present in THIS message: \
name, email, date, time.

Also set "intent" to true if this message expresses a wish to book/schedule an interview, \
OR if it supplies booking-related info (name/email/date/time) even without saying "book" \
explicitly. Otherwise set "intent" to false.

Respond ONLY with raw JSON in exactly this shape, using null for any field not present in \
THIS message:
{"intent": true, "name": null, "email": null, "date": "YYYY-MM-DD", "time": "HH:MM"}

Rules:
- Convert dates to YYYY-MM-DD and times to 24-hour HH:MM.
- If a date is mentioned without a year, still convert what you can (month/day) and leave \
the year out only if truly ambiguous — do not discard the whole field over a missing year.
- If nothing booking-related is present, respond:
  {"intent": false, "name": null, "email": null, "date": null, "time": null}
- Return ONLY raw JSON. No explanation, no markdown, no code fences."""


def _get_groq() -> Groq:
    """Return a shared Groq client instance."""
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client


def extract_booking_fields(user_message: str) -> dict:
    """
    Extract booking-related fields from a SINGLE message only — no history.

    Args:
        user_message: The current turn's raw message text.

    Returns:
        Dict: {"intent": bool, "name": str|None, "email": str|None,
               "date": str|None, "time": str|None}
    """
    client = _get_groq()
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.0,
        max_tokens=150,
    )

    raw: str = response.choices[0].message.content.strip()
    raw = re.sub(r"```json|```", "", raw).strip()

    try:
        result: dict = json.loads(raw)
    except json.JSONDecodeError:
        result = {}

    # Defensive defaults so callers never hit a KeyError
    return {
        "intent": bool(result.get("intent", False)),
        "name": result.get("name") or None,
        "email": result.get("email") or None,
        "date": result.get("date") or None,
        "time": result.get("time") or None,
    }