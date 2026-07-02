"""
Repository layer — all database access goes through here.

This is the data-access tier (the JDBC analog). Business logic and the agent
never touch the ORM session directly; they call these functions, which are
wrapped with the timing and audit aspects and use the `transactional()` scope
so every write is atomic.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import select

from .aspects import audit_log, timed
from .database import transactional
from .models import Reservation, Vehicle


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
@timed
def list_vehicles(vehicle_type: Optional[str] = None) -> list[dict]:
    with transactional() as s:
        stmt = select(Vehicle).order_by(Vehicle.id)
        if vehicle_type:
            stmt = stmt.where(Vehicle.vehicle_type.ilike(vehicle_type))
        return [v.as_dict() for v in s.scalars(stmt)]


@timed
def list_reservations(active_only: bool = False) -> list[dict]:
    with transactional() as s:
        stmt = select(Reservation).order_by(Reservation.start_date)
        if active_only:
            stmt = stmt.where(Reservation.status == "confirmed")
        return [r.as_dict() for r in s.scalars(stmt)]


@timed
def get_reservation(reservation_id: str) -> Optional[dict]:
    with transactional() as s:
        r = s.get(Reservation, reservation_id)
        return r.as_dict() if r else None


# --------------------------------------------------------------------------- #
# Availability engine
# --------------------------------------------------------------------------- #
def _overlaps(s: object, vehicle_id: str, start: dt.date, end: dt.date) -> bool:
    """True if the vehicle has a confirmed reservation overlapping [start, end)."""
    stmt = select(Reservation).where(
        Reservation.vehicle_id == vehicle_id,
        Reservation.status == "confirmed",
        Reservation.start_date < end,
        Reservation.end_date > start,
    )
    return s.scalars(stmt).first() is not None


@timed
@audit_log("availability.check")
def find_available(
    start: dt.date,
    end: dt.date,
    vehicle_type: Optional[str] = None,
) -> list[dict]:
    """Return every operational vehicle free for the whole [start, end) window."""
    with transactional() as s:
        stmt = select(Vehicle).where(Vehicle.status == "available").order_by(Vehicle.id)
        if vehicle_type:
            stmt = stmt.where(Vehicle.vehicle_type.ilike(vehicle_type))
        free: list[dict] = []
        for v in s.scalars(stmt):
            if not _overlaps(s, v.id, start, end):
                free.append(v.as_dict())
        return free


@timed
def is_vehicle_free(vehicle_id: str, start: dt.date, end: dt.date) -> bool:
    with transactional() as s:
        v = s.get(Vehicle, vehicle_id)
        if not v or v.status != "available":
            return False
        return not _overlaps(s, vehicle_id, start, end)


# --------------------------------------------------------------------------- #
# Writes
# --------------------------------------------------------------------------- #
def _next_id(s: object, model, prefix: str, start_num: int) -> str:
    count = s.query(model).count()
    return f"{prefix}-{start_num + count}"


@timed
@audit_log("reservation.create")
def create_reservation(
    vehicle_id: str,
    customer_name: str,
    start: dt.date,
    end: dt.date,
) -> dict:
    """
    Atomically create a reservation, re-checking availability inside the same
    transaction to avoid a double-booking race.
    """
    with transactional() as s:
        v = s.get(Vehicle, vehicle_id)
        if not v:
            raise ValueError(f"Vehicle {vehicle_id} does not exist.")
        if v.status != "available":
            raise ValueError(f"Vehicle {vehicle_id} is not operational ({v.status}).")
        if _overlaps(s, vehicle_id, start, end):
            raise ValueError(f"Vehicle {vehicle_id} is already booked for those dates.")

        new_id = _next_id(s, Reservation, "R", 1001)
        r = Reservation(
            id=new_id,
            vehicle_id=vehicle_id,
            customer_name=customer_name,
            start_date=start,
            end_date=end,
            status="confirmed",
        )
        s.add(r)
        s.flush()
        return r.as_dict()


@timed
@audit_log("reservation.cancel")
def cancel_reservation(reservation_id: str) -> dict:
    with transactional() as s:
        r = s.get(Reservation, reservation_id)
        if not r:
            raise ValueError(f"Reservation {reservation_id} not found.")
        if r.status == "cancelled":
            raise ValueError(f"Reservation {reservation_id} is already cancelled.")
        r.status = "cancelled"
        s.flush()
        return r.as_dict()


@timed
@audit_log("vehicle.register")
def register_vehicle(
    make: str,
    model: str,
    vehicle_type: str,
    registration_number: str,
    daily_rate: float = 0.0,
    location: str = "HQ Depot",
) -> dict:
    with transactional() as s:
        new_id = _next_id(s, Vehicle, "V", 101)
        v = Vehicle(
            id=new_id,
            make=make,
            model=model,
            vehicle_type=vehicle_type,
            registration_number=registration_number,
            daily_rate=daily_rate,
            location=location,
            status="available",
        )
        s.add(v)
        s.flush()
        return v.as_dict()


@timed
def fleet_summary() -> dict:
    """Counts used by the dashboard header."""
    with transactional() as s:
        vehicles = list(s.scalars(select(Vehicle)))
        reservations = list(s.scalars(select(Reservation)))
        return {
            "total_vehicles": len(vehicles),
            "available": sum(1 for v in vehicles if v.status == "available"),
            "maintenance": sum(1 for v in vehicles if v.status == "maintenance"),
            "active_reservations": sum(1 for r in reservations if r.status == "confirmed"),
        }
