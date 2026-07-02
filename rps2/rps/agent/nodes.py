"""
LangGraph node functions.

Each node is a pure-ish function State -> partial State. The `understand` node
runs NLU; a conditional router dispatches to exactly one action node; every
action node writes a structured `result`, a natural-language `reply`, and a
`trace` entry describing what it did.
"""
from __future__ import annotations

import datetime as dt

from .. import repository as repo
from ..nlu import understand
from .state import AgentState


def _trace(node: str, summary: str, detail: dict | None = None) -> list[dict]:
    return [{"node": node, "summary": summary, "detail": detail or {}}]


def _parse_dates(entities: dict) -> tuple[dt.date | None, dt.date | None]:
    s = entities.get("start_date")
    e = entities.get("end_date")
    start = dt.date.fromisoformat(s) if s else None
    end = dt.date.fromisoformat(e) if e else None
    if start and not end:
        end = start + dt.timedelta(days=1)
    return start, end


# --------------------------------------------------------------------------- #
# Understanding
# --------------------------------------------------------------------------- #
def node_understand(state: AgentState) -> AgentState:
    parsed = understand(state["message"])
    return {
        "intent": parsed["intent"],
        "entities": parsed["entities"],
        "nlu_source": parsed["nlu_source"],
        "trace": _trace(
            "understand",
            f"intent={parsed['intent']} via {parsed['nlu_source']}",
            {"entities": parsed["entities"]},
        ),
    }


def route(state: AgentState) -> str:
    """Conditional edge: map the classified intent to an action node name."""
    return {
        "check_availability": "check_availability",
        "create_reservation": "create_reservation",
        "cancel_reservation": "cancel_reservation",
        "list_vehicles": "list_vehicles",
        "list_reservations": "list_reservations",
        "register_vehicle": "register_vehicle",
        "greeting": "smalltalk",
        "help": "smalltalk",
    }.get(state["intent"], "fallback")


# --------------------------------------------------------------------------- #
# Action nodes
# --------------------------------------------------------------------------- #
def node_check_availability(state: AgentState) -> AgentState:
    e = state["entities"]
    start, end = _parse_dates(e)
    vtype = e.get("vehicle_type")

    if not start:
        return {
            "result": {"available": []},
            "reply": "I can check availability — which dates are you looking at? "
                     "For example: \"an SUV next Tuesday for 3 days\".",
            "trace": _trace("check_availability", "missing dates"),
        }

    free = repo.find_available(start, end, vtype)
    window = f"{start.isoformat()} \u2192 {end.isoformat()}"
    if free:
        listed = ", ".join(f"{v['id']} ({v['make']} {v['model']})" for v in free[:6])
        more = "" if len(free) <= 6 else f" and {len(free) - 6} more"
        reply = (
            f"{len(free)} {vtype or 'vehicle'}{'s' if len(free) != 1 else ''} "
            f"free for {window}: {listed}{more}. "
            f"Say e.g. \"book {free[0]['id']} for <name> {window.replace(' \u2192 ', ' to ')}\"."
        )
    else:
        reply = f"No {vtype or 'vehicles'} are free for {window}. Try different dates or another type."

    return {
        "result": {"available": free, "window": window, "vehicle_type": vtype},
        "reply": reply,
        "trace": _trace("check_availability", f"{len(free)} free for {window}",
                        {"vehicle_type": vtype, "count": len(free)}),
    }


def node_create_reservation(state: AgentState) -> AgentState:
    e = state["entities"]
    start, end = _parse_dates(e)
    customer = e.get("customer_name")
    vehicle_id = e.get("vehicle_id")
    vtype = e.get("vehicle_type")

    missing = []
    if not start:
        missing.append("dates")
    if not customer:
        missing.append("a customer name (\"for <name>\")")
    if not vehicle_id and not vtype:
        missing.append("a vehicle or vehicle type")
    if missing:
        return {
            "result": {"status": "needs_info", "missing": missing},
            "reply": "To book I still need " + " and ".join(missing) + ".",
            "trace": _trace("create_reservation", "needs info", {"missing": missing}),
        }

    # If only a type was given, auto-select the first free matching vehicle.
    if not vehicle_id:
        free = repo.find_available(start, end, vtype)
        if not free:
            return {
                "result": {"status": "unavailable"},
                "reply": f"No {vtype} is free for those dates, so I couldn't book one.",
                "trace": _trace("create_reservation", "no inventory"),
            }
        vehicle_id = free[0]["id"]

    try:
        res = repo.create_reservation(vehicle_id, customer, start, end)
        reply = (
            f"Booked. {res['id']}: {vehicle_id} for {customer}, "
            f"{res['start_date']} \u2192 {res['end_date']} ({res['nights']} night"
            f"{'s' if res['nights'] != 1 else ''}). Status: {res['status']}."
        )
        return {
            "result": {"status": "confirmed", "reservation": res},
            "reply": reply,
            "trace": _trace("create_reservation", f"created {res['id']}", {"reservation": res}),
        }
    except ValueError as exc:
        return {
            "result": {"status": "rejected", "error": str(exc)},
            "reply": f"Couldn't book that: {exc}",
            "trace": _trace("create_reservation", "rejected", {"error": str(exc)}),
        }


def node_cancel_reservation(state: AgentState) -> AgentState:
    rid = state["entities"].get("reservation_id")
    if not rid:
        return {
            "result": {"status": "needs_info"},
            "reply": "Which reservation should I cancel? Give me its ID, e.g. \"cancel R-1001\".",
            "trace": _trace("cancel_reservation", "missing id"),
        }
    try:
        res = repo.cancel_reservation(rid)
        return {
            "result": {"status": "cancelled", "reservation": res},
            "reply": f"Cancelled {res['id']} ({res['vehicle_id']} for {res['customer_name']}).",
            "trace": _trace("cancel_reservation", f"cancelled {rid}", {"reservation": res}),
        }
    except ValueError as exc:
        return {
            "result": {"status": "error", "error": str(exc)},
            "reply": f"Couldn't cancel that: {exc}",
            "trace": _trace("cancel_reservation", "error", {"error": str(exc)}),
        }


def node_list_vehicles(state: AgentState) -> AgentState:
    vtype = state["entities"].get("vehicle_type")
    vehicles = repo.list_vehicles(vtype)
    if vehicles:
        lines = ", ".join(f"{v['id']} {v['make']} {v['model']} ({v['status']})" for v in vehicles[:8])
        more = "" if len(vehicles) <= 8 else f" and {len(vehicles) - 8} more"
        reply = f"Fleet ({len(vehicles)} {vtype or 'vehicle'}{'s' if len(vehicles) != 1 else ''}): {lines}{more}."
    else:
        reply = f"No {vtype or 'vehicles'} in the fleet yet."
    return {
        "result": {"vehicles": vehicles},
        "reply": reply,
        "trace": _trace("list_vehicles", f"{len(vehicles)} vehicles", {"vehicle_type": vtype}),
    }


def node_list_reservations(state: AgentState) -> AgentState:
    reservations = repo.list_reservations(active_only=True)
    if reservations:
        lines = "; ".join(
            f"{r['id']} {r['vehicle_id']} {r['customer_name']} {r['start_date']}\u2192{r['end_date']}"
            for r in reservations[:8]
        )
        reply = f"{len(reservations)} active reservation(s): {lines}."
    else:
        reply = "There are no active reservations right now."
    return {
        "result": {"reservations": reservations},
        "reply": reply,
        "trace": _trace("list_reservations", f"{len(reservations)} active"),
    }


def node_register_vehicle(state: AgentState) -> AgentState:
    e = state["entities"]
    make, model = e.get("make"), e.get("model")
    if not make or not model:
        return {
            "result": {"status": "needs_info"},
            "reply": "To onboard a vehicle, tell me the make and model, e.g. "
                     "\"add a Tesla Model 3, type EV, reg KA01AB1234\".",
            "trace": _trace("register_vehicle", "needs info"),
        }
    vtype = e.get("vehicle_type") or "Sedan"
    reg = e.get("registration_number") or f"TMP{abs(hash(make + model)) % 9999:04d}"
    rate = e.get("daily_rate") or 0.0
    v = repo.register_vehicle(make, model, vtype, reg, rate)
    return {
        "result": {"status": "registered", "vehicle": v},
        "reply": f"Onboarded {v['id']}: {make} {model} ({vtype}), reg {reg}.",
        "trace": _trace("register_vehicle", f"registered {v['id']}", {"vehicle": v}),
    }


def node_smalltalk(state: AgentState) -> AgentState:
    reply = (
        "I'm the RPS reservation assistant. I can check availability, book and "
        "cancel reservations, list the fleet, and onboard vehicles. Try: "
        "\"is an SUV free this weekend?\", \"book V-101 for Maria Dec 1 to Dec 4\", "
        "or \"show active reservations\"."
    )
    return {
        "result": {},
        "reply": reply,
        "trace": _trace("smalltalk", state.get("intent", "greeting")),
    }


def node_fallback(state: AgentState) -> AgentState:
    return {
        "result": {},
        "reply": "I didn't quite catch that. I handle vehicle availability, "
                 "reservations, and fleet questions — try \"help\" to see examples.",
        "trace": _trace("fallback", "unrecognised intent"),
    }
