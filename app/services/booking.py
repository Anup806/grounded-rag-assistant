import json
import re

from groq import Groq

from app.core.config import settings

_groq_client: Groq | None = None

_BOOKING_SYSTEM_PROMPT = """You are a booking extraction assistant. Analyze the user message for interview booking intent.

RULES:
1. If the user wants to book an interview AND provides ALL four fields (name, email, date, time), respond ONLY with:
   {"booking": true, "name": "...", "email": "...", "date": "YYYY-MM-DD", "time": "HH:MM"}

2. If the user wants to book but is MISSING one or more fields, respond ONLY with:
   {"booking": false, "missing": ["field1", "field2"]}

3. If there is NO booking intent at all, respond ONLY with:
   {"booking": null}

Return ONLY raw JSON. No explanation, no markdown, no code fences."""


def _get_groq() -> Groq:
    """Return a shared Groq client instance."""
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client


def detect_booking(user_message: str, chat_history: list[dict[str, str]] | None = None) -> dict:
    """
    Use the LLM to detect interview booking intent and extract structured data.

    Args:
        user_message: Raw message text from the user.

    Returns:
        Dict with one of three shapes:
        - {"booking": true, "name": ..., "email": ..., "date": ..., "time": ...}
        - {"booking": false, "missing": [...]}
        - {"booking": null}
    """
    client = _get_groq()

    history_text = ""

    if chat_history:
        recent = chat_history[-8:]  # last 4 turns
        history_text = "\n".join(f"{m['role']}: {m['content']}" for m in recent)

    user_content = (
        f"Conversation history:\n{history_text}\n\nLatest message: {user_message}"
        if history_text
        else user_message
    )

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": _BOOKING_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
        max_tokens=200,
    )

    raw: str = response.choices[0].message.content.strip()

    # Strip markdown code fences if the model adds them despite instructions
    raw = re.sub(r"```json|```", "", raw).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Safe fallback — treat as no booking intent
        return {"booking": None}
