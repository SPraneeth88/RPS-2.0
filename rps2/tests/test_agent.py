"""End-to-end tests: the LangGraph pipeline and the FastAPI surface."""
import datetime as dt

import pytest
from fastapi.testclient import TestClient

from rps import models
from rps.api import app
from rps.database import SessionLocal


@pytest.fixture()
def client(clean_db):
    with SessionLocal() as s:
        s.add(models.Vehicle(id="V-101", make="Toyota", model="RAV4",
                             vehicle_type="SUV", registration_number="R1",
                             status="available"))
        s.commit()
    return TestClient(app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["nlu"] == "rules"


def test_chat_availability_then_book(client):
    today = dt.date.today().isoformat()
    r = client.post("/api/chat", json={"message": "is an SUV available today?"})
    body = r.json()
    assert body["intent"] == "check_availability"
    assert "understand" in [t["node"] for t in body["trace"]]

    r2 = client.post("/api/chat", json={
        "message": f"book V-101 for Jordan Pike from {today} to {today}"
    })
    assert r2.json()["intent"] == "create_reservation"


def test_chat_trace_present(client):
    r = client.post("/api/chat", json={"message": "show me the fleet"})
    body = r.json()
    assert body["intent"] == "list_vehicles"
    assert len(body["trace"]) >= 2


def test_metrics_endpoint(client):
    client.post("/api/chat", json={"message": "is an SUV free today?"})
    data = client.get("/api/metrics").json()
    assert "audit_trail" in data and "latency" in data
