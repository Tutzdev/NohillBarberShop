from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import TimestampMixin
from app.config.extensions import db


class Barber(TimestampMixin, db.Model):
    __tablename__ = "barbers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    services = relationship("BarberService", back_populates="barber", cascade="all, delete-orphan")
    working_hours = relationship(
        "WorkingHour", back_populates="barber", cascade="all, delete-orphan"
    )
    blocked_periods = relationship(
        "BlockedPeriod", back_populates="barber", cascade="all, delete-orphan"
    )
    appointments = relationship("Appointment", back_populates="barber")
