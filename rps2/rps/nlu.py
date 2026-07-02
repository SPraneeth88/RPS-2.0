"""
Natural-language understanding for the reservation assistant.

Two interchangeable back-ends behind one function, `understand()`:

  * LLM mode  — when ANTHROPIC_API_KEY is set, Claude classifies intent and
                extracts entities, resolving relative dates against "today".
  * Rule mode — a deterministic keyword + regex parser used when no key is
                present (offline demos, CI). The LLM path always falls back to
                this on any error, so the assistant never hard-fails.

Both return the same normalised dict, so the rest of the system is agnostic to
which one ran.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from typing import Optional

from .config import settings
from .dateparse import parse_date_range

INTENTS = [
    "check_availability",
    "create_reservation",
    "cancel_reservation",
    "list_vehicles",
    "list_reservations",
    "register_vehicle",
    "greeting",
    "help",
    "unknown",
]

_TYPE_ALIASES = {
    "sedan": "Sedan", "suv": "SUV", "van": "Van", "minivan": "Van",
    "truck": "Truck", "pickup": "Truck", "ev": "EV", "electric": "EV",
}

# Words that can capitalise like a name but are really dates/keywords, so they
# must not leak into a captured customer name (e.g. "book ... for Maria Dec 1").
_NAME_STOPWORDS = {
    "jan", "january", "feb", "february", "mar", "march", "apr", "april", "may",
    "jun", "june", "jul", "july", "aug", "august", "sep", "sept", "september",
    "oct", "october", "nov", "november", "dec", "december",
    "mon", "monday", "tue", "tues", "tuesday", "wed", "wednesday", "thu",
    "thur", "thurs", "thursday", "fri", "friday", "sat", "saturday", "sun",
    "sunday", "today", "tomorrow", "tonight", "next", "this", "from", "to",
}


def _clean_name(raw: str) -> str:
    """Trim trailing date-ish tokens off a captured name."""
    words = raw.strip().split()
    while words and words[-1].lower().strip(".,") in _NAME_STOPWORDS:
        words.pop()
    return " ".join(words)


def _empty_entities() -> dict:
    return {
        "vehicle_type": None,
        "vehicle_id": None,
        "customer_name": None,
        "start_date": None,
        "end_date": None,
        "reservation_id": None,
        "make": None,
        "model": None,
        "registration_number": None,
        "daily_rate": None,
    }


# --------------------------------------------------------------------------- #
# Rule-based parser
# --------------------------------------------------------------------------- #
def _rule_intent(text: str, entities: dict) -> str:
    t = text.lower()

    if re.search(r"\b(hi|hello|hey|good (morning|afternoon|evening))\b", t):
        return "greeting"
    if re.search(r"\b(help|what can you do|how do you work|commands)\b", t):
        return "help"
    if "cancel" in t and entities["reservation_id"]:
        return "cancel_reservation"
    if re.search(r"\b(add|register|onboard)\b", t) and (
        re.search(r"\b(vehicle|car|fleet|van|suv|truck|sedan|ev|electric)\b", t)
        or entities.get("make")
        or entities.get("registration_number")
    ):
        return "register_vehicle"
    if re.search(r"\b(reservation|reservations|bookings|booked|schedule list)\b", t) and not re.search(r"\b(book|reserve|rent)\b", t):
        return "list_reservations"
    if re.search(r"\b(book|reserve|rent|schedule)\b", t):
        return "create_reservation"
    if re.search(r"\b(available|availability|free|open|vacant)\b", t):
        return "check_availability"
    if re.search(r"\b(vehicles?|cars?|fleet|inventory|what do you have)\b", t):
        return "list_vehicles"
    if entities["start_date"]:
        return "check_availability"
    return "unknown"


def _rule_entities(text: str, anchor: dt.date) -> dict:
    e = _empty_entities()

    m = re.search(r"\bV-?(\d+)\b", text, re.I)
    if m:
        e["vehicle_id"] = f"V-{m.group(1)}"
    m = re.search(r"\bR-?(\d+)\b", text, re.I)
    if m:
        e["reservation_id"] = f"R-{m.group(1)}"

    for alias, canonical in _TYPE_ALIASES.items():
        if re.search(rf"\b{alias}s?\b", text, re.I):
            e["vehicle_type"] = canonical
            break

    # Customer name after "for", avoiding "for 3 days"/"for the weekend" and
    # not bleeding into a trailing date token like "Maria Dec ...".
    nm = re.search(r"\bfor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", text)
    if nm and not re.search(r"\b(the|a|an|\d)", nm.group(1).split()[0].lower()):
        e["customer_name"] = _clean_name(nm.group(1))
    nm2 = re.search(r"\b(?:name is|under)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
    if nm2:
        e["customer_name"] = _clean_name(nm2.group(1))

    start, end = parse_date_range(text, anchor)
    if start:
        e["start_date"] = start.isoformat()
    if end:
        e["end_date"] = end.isoformat()

    # Best-effort make/model for registration: "add a Tesla Model 3"
    rm = re.search(
        r"\b(?:add|register|onboard)\s+(?:a\s+|an\s+|the\s+)?([A-Z][\w\-]+)\s+([^,]+?)"
        r"(?=,|\s+(?:type|reg|plate|registration|located|priced|to|with)\b|$)",
        text,
    )
    if rm:
        e["make"] = rm.group(1).strip()
        e["model"] = rm.group(2).strip()
    plate = re.search(r"\b(?:reg|plate|registration)\b\.?\s*#?\s*([A-Z0-9]{5,12})\b", text, re.I)
    if plate:
        e["registration_number"] = plate.group(1).upper()
    rate = re.search(r"\$?\s*(\d+(?:\.\d+)?)\s*(?:/day|per day|daily)", text, re.I)
    if rate:
        e["daily_rate"] = float(rate.group(1))

    return e


def _rule_understand(message: str, anchor: dt.date) -> dict:
    entities = _rule_entities(message, anchor)
    intent = _rule_intent(message, entities)
    return {"intent": intent, "entities": entities, "nlu_source": "rules"}


# --------------------------------------------------------------------------- #
# LLM parser
# --------------------------------------------------------------------------- #
_SYSTEM = """You are the intent + entity extractor for a vehicle Reservation \
Processing System. Read the user message and respond with ONLY a JSON object \
(no markdown, no prose) with this exact shape:

{{
  "intent": one of {intents},
  "entities": {{
    "vehicle_type": "Sedan"|"SUV"|"Van"|"Truck"|"EV"|null,
    "vehicle_id": string like "V-101" or null,
    "customer_name": string or null,
    "start_date": "YYYY-MM-DD" or null,
    "end_date": "YYYY-MM-DD" or null,
    "reservation_id": string like "R-1001" or null,
    "make": string or null,
    "model": string or null,
    "registration_number": string or null,
    "daily_rate": number or null
  }}
}}

Today's date is {today} ({weekday}). Resolve every relative date (e.g. "next \
Tuesday", "this weekend", "tomorrow") to an absolute YYYY-MM-DD. If only a \
start date and a duration are given, compute end_date = start + duration. \
Default a single-day request to a 1-day window. Output JSON only."""


def _llm_understand(message: str, anchor: dt.date) -> Optional[dict]:
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        system = _SYSTEM.format(
            intents=INTENTS,
            today=anchor.isoformat(),
            weekday=anchor.strftime("%A"),
        )
        resp = client.messages.create(
            model=settings.llm_model,
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": message}],
        )
        raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip()).strip()
        data = json.loads(raw)

        entities = _empty_entities()
        entities.update({k: v for k, v in data.get("entities", {}).items() if k in entities})
        intent = data.get("intent", "unknown")
        if intent not in INTENTS:
            intent = "unknown"
        return {"intent": intent, "entities": entities, "nlu_source": "llm"}
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def understand(message: str, anchor: Optional[dt.date] = None) -> dict:
    anchor = anchor or dt.date.today()
    if settings.llm_enabled:
        parsed = _llm_understand(message, anchor)
        if parsed is not None:
            return parsed
    return _rule_understand(message, anchor)
