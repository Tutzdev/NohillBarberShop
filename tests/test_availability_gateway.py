from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

import pytest

from app.appointments.models import Appointment, AppointmentStatus
from app.availability.gateway import SqlAlchemyAvailabilityGateway
from app.availability.models import BarberService, BlockedPeriod, WorkingHour
from app.barbers.models import Barber
from app.config.extensions import db
from app.customers.models import Customer
from app.integrations.availability import AvailabilityStatus
from app.services.models import Service

MONDAY_NINE_AM = datetime(2026, 8, 24, 12, tzinfo=UTC)


@pytest.fixture
def availability_data(app):
    with app.app_context():
        barber = Barber(name="Vitor")
        service = Service(name="Corte", duration_minutes=30, active=True)
        db.session.add_all([barber, service])
        db.session.flush()
        db.session.add_all(
            [
                BarberService(barber_id=barber.id, service_id=service.id),
                WorkingHour(
                    barber_id=barber.id,
                    weekday=0,
                    start_time=time(9),
                    end_time=time(18),
                ),
            ]
        )
        db.session.commit()
        return {"barber_id": barber.id, "service_id": service.id}


def check(data, start_at=MONDAY_NINE_AM, **kwargs):
    return SqlAlchemyAvailabilityGateway().check(
        barber_id=data["barber_id"],
        service_id=data["service_id"],
        start_at=start_at,
        **kwargs,
    )


def test_returns_not_found_statuses(app, availability_data):
    with app.app_context():
        missing_barber = SqlAlchemyAvailabilityGateway().check(
            barber_id=999,
            service_id=availability_data["service_id"],
            start_at=MONDAY_NINE_AM,
        )
        missing_service = SqlAlchemyAvailabilityGateway().check(
            barber_id=availability_data["barber_id"], service_id=999, start_at=MONDAY_NINE_AM
        )

    assert missing_barber.status is AvailabilityStatus.BARBER_NOT_FOUND
    assert missing_barber.end_at is None
    assert missing_service.status is AvailabilityStatus.SERVICE_NOT_FOUND
    assert missing_service.end_at is None


def test_available_slot_uses_service_duration_and_utc(app, availability_data):
    with app.app_context():
        decision = check(availability_data)

    assert decision.status is AvailabilityStatus.AVAILABLE
    assert decision.end_at == MONDAY_NINE_AM + timedelta(minutes=30)
    assert decision.end_at.tzinfo is not None


def test_rejects_outside_working_hours(app, availability_data):
    with app.app_context():
        decision = check(availability_data, MONDAY_NINE_AM - timedelta(minutes=1))

    assert decision.status is AvailabilityStatus.UNAVAILABLE


def test_rejects_inactive_barber_and_unlinked_service(app, availability_data):
    with app.app_context():
        barber = db.session.get(Barber, availability_data["barber_id"])
        barber.active = False
        inactive = check(availability_data)
        barber.active = True
        other_service = Service(name="Barba", duration_minutes=20, active=True)
        db.session.add(other_service)
        db.session.commit()
        unlinked = SqlAlchemyAvailabilityGateway().check(
            barber_id=barber.id,
            service_id=other_service.id,
            start_at=MONDAY_NINE_AM,
        )

    assert inactive.status is AvailabilityStatus.UNAVAILABLE
    assert unlinked.status is AvailabilityStatus.UNAVAILABLE


def test_rejects_blocked_period_overlap(app, availability_data):
    with app.app_context():
        db.session.add(
            BlockedPeriod(
                barber_id=availability_data["barber_id"],
                start_at=MONDAY_NINE_AM + timedelta(minutes=15),
                end_at=MONDAY_NINE_AM + timedelta(hours=1),
            )
        )
        db.session.commit()
        decision = check(availability_data)

    assert decision.status is AvailabilityStatus.UNAVAILABLE


def test_scheduled_appointments_overlap_but_adjacent_ones_do_not(app, availability_data):
    with app.app_context():
        customer = Customer(
            name="Cliente", email="cliente@example.com", phone="11999999999", password_hash="hash"
        )
        db.session.add(customer)
        db.session.flush()
        appointment = Appointment(
            customer_id=customer.id,
            barber_id=availability_data["barber_id"],
            service_id=availability_data["service_id"],
            start_at=MONDAY_NINE_AM,
            end_at=MONDAY_NINE_AM + timedelta(minutes=30),
            status=AppointmentStatus.SCHEDULED,
        )
        db.session.add(appointment)
        db.session.commit()
        overlap = check(availability_data, MONDAY_NINE_AM + timedelta(minutes=15))
        adjacent = check(availability_data, MONDAY_NINE_AM + timedelta(minutes=30))
        ignored_current = check(
            availability_data,
            MONDAY_NINE_AM,
            exclude_appointment_id=appointment.id,
        )

    assert overlap.status is AvailabilityStatus.UNAVAILABLE
    assert adjacent.status is AvailabilityStatus.AVAILABLE
    assert ignored_current.status is AvailabilityStatus.AVAILABLE


def test_cancelled_appointment_does_not_block_slot(app, availability_data):
    with app.app_context():
        customer = Customer(
            name="Cliente", email="cancelled@example.com", phone="11999999999", password_hash="hash"
        )
        db.session.add(customer)
        db.session.flush()
        db.session.add(
            Appointment(
                customer_id=customer.id,
                barber_id=availability_data["barber_id"],
                service_id=availability_data["service_id"],
                start_at=MONDAY_NINE_AM,
                end_at=MONDAY_NINE_AM + timedelta(minutes=30),
                status=AppointmentStatus.CANCELLED,
            )
        )
        db.session.commit()
        decision = check(availability_data)

    assert decision.status is AvailabilityStatus.AVAILABLE
