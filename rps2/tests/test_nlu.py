"""NLU intent/entity + date-parser tests (rule-based path, deterministic anchor)."""
import datetime as dt

from rps.dateparse import parse_date_range
from rps.nlu import _rule_understand

ANCHOR = dt.date(2025, 12, 1)  # a Monday


def u(msg):
    return _rule_understand(msg, ANCHOR)


def test_intent_greeting_and_help():
    assert u("hello there")["intent"] == "greeting"
    assert u("what can you do?")["intent"] == "help"


def test_intent_check_availability():
    r = u("is an SUV available this weekend?")
    assert r["intent"] == "check_availability"
    assert r["entities"]["vehicle_type"] == "SUV"


def test_intent_create_with_entities():
    r = u("book V-104 for Sarah Connor from Dec 3 to Dec 6")
    assert r["intent"] == "create_reservation"
    e = r["entities"]
    assert e["vehicle_id"] == "V-104"
    assert e["customer_name"] == "Sarah Connor"
    assert e["start_date"] == "2025-12-03"
    assert e["end_date"] == "2025-12-06"


def test_intent_cancel():
    r = u("please cancel R-1002")
    assert r["intent"] == "cancel_reservation"
    assert r["entities"]["reservation_id"] == "R-1002"


def test_register_extraction():
    r = u("add a Tesla Model 3, type EV, reg KA01AB1234")
    assert r["intent"] == "register_vehicle"
    e = r["entities"]
    assert e["make"] == "Tesla"
    assert e["model"] == "Model 3"
    assert e["registration_number"] == "KA01AB1234"


def test_dateparse_relative_weekday():
    # From Monday Dec 1, the next upcoming Tuesday is Dec 2.
    start, end = parse_date_range("next tuesday for 3 days", ANCHOR)
    assert start == dt.date(2025, 12, 2)
    assert end == dt.date(2025, 12, 5)


def test_dateparse_weekend():
    start, end = parse_date_range("this weekend", ANCHOR)
    assert start.weekday() == 5  # Saturday
    assert (end - start).days == 2


def test_dateparse_explicit_range():
    start, end = parse_date_range("from Dec 10 to Dec 14", ANCHOR)
    assert start == dt.date(2025, 12, 10)
    assert end == dt.date(2025, 12, 14)


def test_dateparse_tomorrow():
    start, _ = parse_date_range("tomorrow for 2 days", ANCHOR)
    assert start == dt.date(2025, 12, 2)
