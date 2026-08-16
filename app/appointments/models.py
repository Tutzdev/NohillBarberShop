from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import TimestampMixin
from app.config.extensions import db


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


appointment_status_type = Enum(
    AppointmentStatus,
    values_callable=lambda enum: [item.value for item in enum],
    native_enum=False,
    length=20,
    name="appointment_status",
)


class Appointment(TimestampMixin, db.Model):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="positive_duration"),
        Index(
            "uq_appointments_active_barber_start",
            "barber_id",
            "start_at",
            unique=True,
            sqlite_where=text("status = 'scheduled'"),
            postgresql_where=text("status = 'scheduled'"),
        ),
        Index("ix_appointments_customer_start", "customer_id", "start_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    # Foreign keys are added when Vitor's real barber/service tables and names are available.
    barber_id: Mapped[int] = mapped_column(nullable=False, index=True)
    service_id: Mapped[int] = mapped_column(nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        appointment_status_type, default=AppointmentStatus.SCHEDULED, nullable=False
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version_id: Mapped[int] = mapped_column(nullable=False, default=1)

    customer = relationship("Customer", back_populates="appointments")
    __mapper_args__ = {"version_id_col": version_id}
