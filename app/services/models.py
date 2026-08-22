from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import TimestampMixin
from app.config.extensions import db


class Service(TimestampMixin, db.Model):
    __tablename__ = "services"
    __table_args__ = (CheckConstraint("duration_minutes > 0", name="positive_duration"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Service is the sole official source for a booking duration.
    duration_minutes: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    barbers = relationship("BarberService", back_populates="service", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="service")
