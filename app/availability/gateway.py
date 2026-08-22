from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import exists

from app.appointments.models import Appointment, AppointmentStatus
from app.availability.models import BarberService, BlockedPeriod, WorkingHour
from app.barbers.models import Barber
from app.common.time import as_utc
from app.config.extensions import db
from app.integrations.availability import AvailabilityDecision, AvailabilityStatus
from app.services.models import Service

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


class SqlAlchemyAvailabilityGateway:
    """Authoritative, transaction-bound availability validation."""

    def check(
        self,
        *,
        barber_id: int,
        service_id: int,
        start_at: datetime,
        exclude_appointment_id: int | None = None,
    ) -> AvailabilityDecision:
        requested_start = as_utc(start_at)
        barber = db.session.get(Barber, barber_id)
        if barber is None:
            return AvailabilityDecision(AvailabilityStatus.BARBER_NOT_FOUND)
        if not barber.active:
            return AvailabilityDecision(AvailabilityStatus.UNAVAILABLE)

        service = db.session.get(Service, service_id)
        if service is None:
            return AvailabilityDecision(AvailabilityStatus.SERVICE_NOT_FOUND)
        if not service.active or service.duration_minutes <= 0:
            return AvailabilityDecision(AvailabilityStatus.UNAVAILABLE)

        linked = db.session.scalar(
            db.select(
                exists().where(
                    BarberService.barber_id == barber_id,
                    BarberService.service_id == service_id,
                )
            )
        )
        if not linked:
            return AvailabilityDecision(AvailabilityStatus.UNAVAILABLE)

        requested_end = requested_start + timedelta(minutes=service.duration_minutes)
        if not self._within_working_hours(barber_id, requested_start, requested_end):
            return AvailabilityDecision(AvailabilityStatus.UNAVAILABLE)
        if self._has_blocked_period(barber_id, requested_start, requested_end):
            return AvailabilityDecision(AvailabilityStatus.UNAVAILABLE)
        if self._has_scheduled_conflict(
            barber_id, requested_start, requested_end, exclude_appointment_id
        ):
            return AvailabilityDecision(AvailabilityStatus.UNAVAILABLE)
        return AvailabilityDecision(AvailabilityStatus.AVAILABLE, requested_end.astimezone(UTC))

    @staticmethod
    def _within_working_hours(barber_id: int, start_at: datetime, end_at: datetime) -> bool:
        local_start = start_at.astimezone(SAO_PAULO)
        local_end = end_at.astimezone(SAO_PAULO)
        if local_start.date() != local_end.date():
            return False
        windows = db.session.scalars(
            db.select(WorkingHour).where(
                WorkingHour.barber_id == barber_id,
                WorkingHour.weekday == local_start.weekday(),
                WorkingHour.start_time <= local_start.timetz().replace(tzinfo=None),
                WorkingHour.end_time >= local_end.timetz().replace(tzinfo=None),
            )
        )
        return next(windows, None) is not None

    @staticmethod
    def _has_blocked_period(barber_id: int, start_at: datetime, end_at: datetime) -> bool:
        return db.session.scalar(
            db.select(
                exists().where(
                    BlockedPeriod.barber_id == barber_id,
                    BlockedPeriod.start_at < end_at,
                    BlockedPeriod.end_at > start_at,
                )
            )
        )

    @staticmethod
    def _has_scheduled_conflict(
        barber_id: int,
        start_at: datetime,
        end_at: datetime,
        exclude_appointment_id: int | None,
    ) -> bool:
        conditions = [
            Appointment.barber_id == barber_id,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.start_at < end_at,
            Appointment.end_at > start_at,
        ]
        if exclude_appointment_id is not None:
            conditions.append(Appointment.id != exclude_appointment_id)
        return db.session.scalar(db.select(exists().where(*conditions)))
