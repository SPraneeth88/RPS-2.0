"""
Populate the database with a realistic sample fleet and a few reservations so
the prototype has something to show the moment it boots.

Run directly:  python seed_data.py
"""
from __future__ import annotations

import datetime as dt

from rps.database import SessionLocal, init_db
from rps.models import Reservation, Vehicle

FLEET = [
    ("V-101", "Toyota", "Camry", "Sedan", "KA01AA1010", "HQ Depot", 48.0, "available"),
    ("V-102", "Honda", "Accord", "Sedan", "KA01AA1020", "HQ Depot", 50.0, "available"),
    ("V-103", "Toyota", "RAV4", "SUV", "KA01BB2030", "North Hub", 72.0, "available"),
    ("V-104", "Jeep", "Grand Cherokee", "SUV", "KA01BB2040", "North Hub", 95.0, "available"),
    ("V-105", "Ford", "Transit", "Van", "KA01CC3050", "HQ Depot", 88.0, "available"),
    ("V-106", "Mercedes", "Sprinter", "Van", "KA01CC3060", "South Hub", 110.0, "maintenance"),
    ("V-107", "Ford", "F-150", "Truck", "KA01DD4070", "South Hub", 130.0, "available"),
    ("V-108", "Tesla", "Model 3", "EV", "KA01EE5080", "HQ Depot", 99.0, "available"),
    ("V-109", "Tesla", "Model Y", "EV", "KA01EE5090", "North Hub", 120.0, "available"),
    ("V-110", "Hyundai", "Tucson", "SUV", "KA01BB2100", "HQ Depot", 68.0, "available"),
]


def seed() -> None:
    init_db()
    today = dt.date.today()
    with SessionLocal() as s:
        # Idempotent: clear and rebuild so re-seeding is safe.
        s.query(Reservation).delete()
        s.query(Vehicle).delete()
        s.commit()

        for vid, make, model, vtype, reg, loc, rate, status in FLEET:
            s.add(Vehicle(
                id=vid, make=make, model=model, vehicle_type=vtype,
                registration_number=reg, location=loc, daily_rate=rate, status=status,
            ))

        sample_res = [
            ("R-1001", "V-101", "Aanya Rao", today + dt.timedelta(days=1), today + dt.timedelta(days=4)),
            ("R-1002", "V-103", "Mark Lee", today + dt.timedelta(days=2), today + dt.timedelta(days=3)),
            ("R-1003", "V-108", "Priya Nair", today + dt.timedelta(days=5), today + dt.timedelta(days=9)),
        ]
        for rid, vid, cust, start, end in sample_res:
            s.add(Reservation(
                id=rid, vehicle_id=vid, customer_name=cust,
                start_date=start, end_date=end, status="confirmed",
            ))
        s.commit()

    print(f"Seeded {len(FLEET)} vehicles and 3 reservations into the database.")


if __name__ == "__main__":
    seed()
