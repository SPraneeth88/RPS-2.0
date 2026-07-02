"""Repository + availability-engine tests."""
import datetime as dt

import pytest

from rps import models, repository
from rps.database import SessionLocal


@pytest.fixture()
def repo(clean_db):
    with SessionLocal() as s:
        s.add(models.Vehicle(id="V-1", make="Toyota", model="Camry",
                             vehicle_type="Sedan", registration_number="R1",
                             status="available"))
        s.add(models.Vehicle(id="V-2", make="Jeep", model="GC",
                             vehicle_type="SUV", registration_number="R2",
                             status="maintenance"))
        s.commit()
    return repository


def test_available_excludes_maintenance(repo):
    today = dt.date.today()
    free = repo.find_available(today, today + dt.timedelta(days=2))
    ids = [v["id"] for v in free]
    assert "V-1" in ids
    assert "V-2" not in ids


def test_create_and_overlap_block(repo):
    today = dt.date.today()
    a, b = today + dt.timedelta(days=1), today + dt.timedelta(days=4)
    res = repo.create_reservation("V-1", "Alice", a, b)
    assert res["status"] == "confirmed"
    assert repo.is_vehicle_free("V-1", a + dt.timedelta(days=1), b) is False
    with pytest.raises(ValueError):
        repo.create_reservation("V-1", "Bob", a, b)


def test_adjacent_booking_allowed(repo):
    today = dt.date.today()
    a, b = today + dt.timedelta(days=1), today + dt.timedelta(days=3)
    repo.create_reservation("V-1", "Alice", a, b)
    res = repo.create_reservation("V-1", "Carol", b, b + dt.timedelta(days=2))
    assert res["status"] == "confirmed"


def test_cancel_frees_vehicle(repo):
    today = dt.date.today()
    a, b = today + dt.timedelta(days=1), today + dt.timedelta(days=3)
    res = repo.create_reservation("V-1", "Alice", a, b)
    repo.cancel_reservation(res["id"])
    assert repo.is_vehicle_free("V-1", a, b) is True
