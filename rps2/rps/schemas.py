"""Pydantic schemas for the API surface."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    session_id: str = "demo"


class ChatResponse(BaseModel):
    reply: str
    intent: str
    entities: dict
    nlu_source: str
    result: dict
    trace: list


class VehicleCreate(BaseModel):
    make: str
    model: str
    vehicle_type: str = "Sedan"
    registration_number: str
    daily_rate: float = 0.0
    location: str = "HQ Depot"
