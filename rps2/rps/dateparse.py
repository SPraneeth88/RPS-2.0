"""
Tiny natural-language date parser.

Handles the date expressions a reservation user actually types — "next Tuesday",
"Dec 1", "this weekend", "for 3 days", "12/05/2025", ISO dates, ranges like
"Dec 1 to Dec 5" — without pulling in a heavyweight NLP date library. It is
deliberately small and deterministic so it works offline and is easy to test.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Optional, Tuple

_WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2,
    "wed": 2, "thursday": 3, "thu": 3, "thurs": 3, "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def _next_weekday(anchor: dt.date, weekday: int, force_next: bool) -> dt.date:
    # Resolve to the next upcoming occurrence of `weekday`; if today already is
    # that weekday, jump to the following week (you can't reserve into the past).
    delta = (weekday - anchor.weekday()) % 7
    if delta == 0:
        delta = 7
    return anchor + dt.timedelta(days=delta)


def _parse_single(token: str, anchor: dt.date) -> Optional[dt.date]:
    """Resolve one date expression to a concrete date, or None."""
    t = token.strip().lower()
    if not t:
        return None

    if re.search(r"\b(today|tonight)\b", t):
        return anchor
    if re.search(r"\btomorrow\b", t):
        return anchor + dt.timedelta(days=1)

    # ISO  2025-12-01
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # Numeric  12/05  or  12/05/2025
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else anchor.year
        if year < 100:
            year += 2000
        cand = dt.date(year, month, day)
        if not m.group(3) and cand < anchor:
            cand = cand.replace(year=year + 1)
        return cand

    # "next friday" / "this friday" / "friday"
    force_next = "next" in t
    for name, wd in _WEEKDAYS.items():
        if re.search(rf"\b{name}\b", t):
            return _next_weekday(anchor, wd, force_next)

    # "dec 1", "december 1 2025", "1 dec"
    for name, mon in _MONTHS.items():
        if re.search(rf"\b{name}\b", t):
            dm = re.search(rf"{name}\s+(\d{{1,2}})", t) or re.search(rf"(\d{{1,2}})\s+{name}", t)
            if dm:
                day = int(dm.group(1))
                ym = re.search(r"\b(20\d{2})\b", t)
                year = int(ym.group(1)) if ym else anchor.year
                cand = dt.date(year, mon, day)
                if not ym and cand < anchor:
                    cand = cand.replace(year=year + 1)
                return cand
    return None


def _extract_duration(text: str) -> Optional[int]:
    """Number of days from 'for 3 days', '3-day', '3 nights', 'a week', 'the weekend'."""
    t = text.lower()
    if "weekend" in t:
        return 2
    if re.search(r"\b(a|one)\s+week\b", t) or "week-long" in t:
        return 7
    m = re.search(r"\b(\d+)\s*[- ]?\s*(day|days|night|nights)\b", t)
    if m:
        return int(m.group(1))
    return None


def parse_date_range(
    text: str,
    anchor: Optional[dt.date] = None,
) -> Tuple[Optional[dt.date], Optional[dt.date]]:
    """
    Best-effort extraction of (start, end) from free text.

    Returns (None, None) if no start can be found. End defaults to start + the
    detected duration, or start + 1 day if none is given.
    """
    anchor = anchor or dt.date.today()
    low = text.lower()

    # Explicit range:  "from X to Y" / "X to Y" / "X - Y" / "X until Y"
    range_match = re.search(
        r"(?:from\s+)?(.+?)\s+(?:to|until|till|through|thru|-|—)\s+(.+)",
        low,
    )
    if range_match:
        start = _parse_single(range_match.group(1), anchor)
        end = _parse_single(range_match.group(2), anchor)
        if start and end and end > start:
            return start, end
        if start and not end:  # second half was a duration, fall through
            pass

    # "this weekend" special case
    if "weekend" in low:
        sat = _next_weekday(anchor, 5, force_next=False)
        if anchor.weekday() in (5, 6):
            sat = anchor
        return sat, sat + dt.timedelta(days=2)

    start = _parse_single(low, anchor)
    if not start:
        return None, None

    duration = _extract_duration(low) or 1
    return start, start + dt.timedelta(days=duration)
