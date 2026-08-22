from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import TimestampMixin
from app.config.extensions import db


class BarberService(db.Model):
    __tablename__ = "barber_services"
    __table_args__ = (UniqueConstraint("barber_id", "service_id", name="barber_service"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    barber_id: Mapped[int] = mapped_column(ForeignKey("barbers.id"), nullable=False, index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=False, index=True)

    barber = relationship("Barber", back_populates="services")
    service = relationship("Service", back_populates="barbers")


class WorkingHour(TimestampMixin, db.Model):
    __tablename__ = "working_hours"
    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="valid_weekday"),
        CheckConstraint("end_time > start_time", name="positive_interval"),
        Index("ix_working_hours_barber_weekday", "barber_id", "weekday"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    barber_id: Mapped[int] = mapped_column(ForeignKey("barbers.id"), nullable=False, index=True)
    # Monday is 0, matching datetime.weekday(). Multiple rows allow pauses in a day.
    weekday: Mapped[int] = mapped_column(nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    barber = relationship("Barber", back_populates="working_hours")


class BlockedPeriod(TimestampMixin, db.Model):
    __tablename__ = "blocked_periods"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="positive_interval"),
        Index("ix_blocked_periods_barber_start_end", "barber_id", "start_at", "end_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    barber_id: Mapped[int] = mapped_column(ForeignKey("barbers.id"), nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))

    barber = relationship("Barber", back_populates="blocked_periods")
