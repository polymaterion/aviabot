from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base


class Flight(Base):
    """Единый внутренний формат авиабилета, полученного от провайдера."""

    __tablename__ = "flights"

    id: Mapped[int] = mapped_column(primary_key=True)

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    airline: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    flight_number: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    origin: Mapped[str] = mapped_column(String(8), nullable=False)
    destination: Mapped[str] = mapped_column(String(8), nullable=False)

    departure_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    arrival_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    return_departure_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    return_arrival_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)

    direct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    duration: Mapped[Optional[int]] = mapped_column(nullable=True)  # minutes
    baggage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    booking_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    parsed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
