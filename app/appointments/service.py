from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.appointments.models import Appointment, AppointmentStatus
from app.common.errors import APIError, ConflictError, NotFoundError
from app.common.time import as_utc, utc_now
from app.config.extensions import db
from app.customers.models import Customer
from app.integrations.availability import (
    AvailabilityDecision,
    AvailabilityStatus,
    get_availability_gateway,
)


def create_appointment(
    customer: Customer, *, barber_id: int, service_id: int, start_at: datetime
) -> Appointment:
    normalized_start = _validate_future_start(start_at)
    _acquire_barber_lock(barber_id)
    decision = get_availability_gateway().check(
        barber_id=barber_id,
        service_id=service_id,
        start_at=normalized_start,
    )
    end_at = _available_end_or_raise(decision, normalized_start)

    appointment = Appointment(
        customer_id=customer.id,
        barber_id=barber_id,
        service_id=service_id,
        start_at=normalized_start,
        end_at=end_at,
    )
    db.session.add(appointment)
    _commit_slot_change()
    return appointment


def get_customer_appointment(customer: Customer, appointment_id: int) -> Appointment:
    appointment = db.session.scalar(
        db.select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.customer_id == customer.id,
        )
    )
    if appointment is None:
        raise NotFoundError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.")
    return appointment


def list_customer_appointments(
    customer: Customer, *, page: int, per_page: int, status: str | None = None
) -> tuple[list[Appointment], int]:
    statement = db.select(Appointment).where(Appointment.customer_id == customer.id)
    if status:
        statement = statement.where(Appointment.status == AppointmentStatus(status))
    statement = statement.order_by(Appointment.start_at.desc())
    pagination = db.paginate(statement, page=page, per_page=per_page, error_out=False)
    return list(pagination.items), pagination.total


def cancel_appointment(customer: Customer, appointment_id: int) -> Appointment:
    appointment = get_customer_appointment(customer, appointment_id)
    if appointment.status is not AppointmentStatus.SCHEDULED:
        raise ConflictError(
            "INVALID_APPOINTMENT_STATE", "Somente agendamentos ativos podem ser cancelados."
        )
    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancelled_at = utc_now()
    _commit_state_change()
    return appointment


def reschedule_appointment(
    customer: Customer, appointment_id: int, *, start_at: datetime
) -> Appointment:
    appointment = get_customer_appointment(customer, appointment_id)
    if appointment.status is not AppointmentStatus.SCHEDULED:
        raise ConflictError(
            "INVALID_APPOINTMENT_STATE", "Somente agendamentos ativos podem ser reagendados."
        )

    normalized_start = _validate_future_start(start_at)
    _acquire_barber_lock(appointment.barber_id)
    decision = get_availability_gateway().check(
        barber_id=appointment.barber_id,
        service_id=appointment.service_id,
        start_at=normalized_start,
        exclude_appointment_id=appointment.id,
    )
    end_at = _available_end_or_raise(decision, normalized_start)
    appointment.start_at = normalized_start
    appointment.end_at = end_at
    _commit_slot_change()
    return appointment


def _validate_future_start(start_at: datetime) -> datetime:
    try:
        normalized = as_utc(start_at)
    except ValueError as exc:
        raise APIError("INVALID_DATETIME", "start_at deve incluir o fuso horário.", 422) from exc
    if normalized <= utc_now():
        raise APIError("INVALID_DATETIME", "start_at deve estar no futuro.", 422)
    return normalized


def _available_end_or_raise(decision: AvailabilityDecision, start_at: datetime) -> datetime:
    if decision.status is AvailabilityStatus.BARBER_NOT_FOUND:
        raise NotFoundError("BARBER_NOT_FOUND", "Barbeiro não encontrado.")
    if decision.status is AvailabilityStatus.SERVICE_NOT_FOUND:
        raise NotFoundError("SERVICE_NOT_FOUND", "Serviço não encontrado.")
    if decision.status is AvailabilityStatus.UNAVAILABLE:
        raise ConflictError("TIME_SLOT_UNAVAILABLE", "O horário selecionado não está disponível.")
    if decision.status is not AvailabilityStatus.AVAILABLE or decision.end_at is None:
        raise APIError(
            "INVALID_AVAILABILITY_RESPONSE",
            "A integração de disponibilidade retornou uma resposta inválida.",
            502,
        )
    try:
        end_at = as_utc(decision.end_at)
    except ValueError as exc:
        raise APIError(
            "INVALID_AVAILABILITY_RESPONSE",
            "A integração de disponibilidade retornou uma data inválida.",
            502,
        ) from exc
    if end_at <= start_at:
        raise APIError(
            "INVALID_AVAILABILITY_RESPONSE",
            "A integração de disponibilidade retornou uma duração inválida.",
            502,
        )
    return end_at


def _acquire_barber_lock(barber_id: int) -> None:
    if db.session.get_bind().dialect.name == "postgresql":
        db.session.execute(
            text("SELECT pg_advisory_xact_lock(:namespace, :barber_id)"),
            {"namespace": 1313818696, "barber_id": barber_id},
        )


def _commit_slot_change() -> None:
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ConflictError(
            "TIME_SLOT_UNAVAILABLE", "O horário selecionado não está mais disponível."
        ) from exc
    except StaleDataError as exc:
        db.session.rollback()
        raise ConflictError(
            "APPOINTMENT_CHANGED",
            "O agendamento foi alterado por outra operação. Atualize os dados e tente novamente.",
        ) from exc


def _commit_state_change() -> None:
    try:
        db.session.commit()
    except StaleDataError as exc:
        db.session.rollback()
        raise ConflictError(
            "APPOINTMENT_CHANGED",
            "O agendamento foi alterado por outra operação. Atualize os dados e tente novamente.",
        ) from exc
