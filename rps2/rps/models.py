"""ORM models: the core domain entities of the reservation system."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # e.g. "V-101"
    make: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(40))
    vehicle_type: Mapped[str] = mapped_column(String(20))  # Sedan / SUV / Van / Truck / EV
    registration_number: Mapped[str] = mapped_column(String(20), unique=True)
    location: Mapped[str] = mapped_column(String(40), default="HQ Depot")
    daily_rate: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="available")  # available / maintenance / retired

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="vehicle")

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "make": self.make,
            "model": self.model,
            "vehicle_type": self.vehicle_type,
            "registration_number": self.registration_number,
            "location": self.location,
            "daily_rate": self.daily_rate,
            "status": self.status,
        }


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # e.g. "R-1001"
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"))
    customer_name: Mapped[str] = mapped_column(String(80))
    start_date: Mapped[dt.date] = mapped_column(Date)
    end_date: Mapped[dt.date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="confirmed")  # confirmed / cancelled / completed
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    vehicle: Mapped["Vehicle"] = relationship(back_populates="reservations")

    @property
    def nights(self) -> int:
        return max(1, (self.end_date - self.start_date).days)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "customer_name": self.customer_name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "status": self.status,
            "nights": self.nights,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
