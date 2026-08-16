from __future__ import annotations

from datetime import timedelta

from app.appointments.models import Appointment
from app.config.extensions import db
from app.integrations.availability import AvailabilityStatus
from tests.conftest import login, register


def appointment_payload(future_start):
    return {
        "barber_id": 10,
        "service_id": 20,
        "start_at": future_start.isoformat(),
    }


def create_appointment(client, auth_headers, future_start):
    return client.post(
        "/api/appointments",
        headers=auth_headers,
        json=appointment_payload(future_start),
    )


def test_create_appointment_uses_availability_gateway(
    client, auth_headers, availability, future_start
):
    response = create_appointment(client, auth_headers, future_start)

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["status"] == "scheduled"
    assert availability.calls[0]["barber_id"] == 10
    assert availability.calls[0]["service_id"] == 20


def test_create_appointment_requires_authentication(client, future_start):
    response = client.post("/api/appointments", json=appointment_payload(future_start))
    assert response.status_code == 401


def test_create_appointment_maps_invalid_barber(client, auth_headers, availability, future_start):
    availability.status = AvailabilityStatus.BARBER_NOT_FOUND
    response = create_appointment(client, auth_headers, future_start)
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "BARBER_NOT_FOUND"


def test_create_appointment_maps_invalid_service(client, auth_headers, availability, future_start):
    availability.status = AvailabilityStatus.SERVICE_NOT_FOUND
    response = create_appointment(client, auth_headers, future_start)
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "SERVICE_NOT_FOUND"


def test_create_appointment_rejects_unavailable_slot(
    client, auth_headers, availability, future_start
):
    availability.status = AvailabilityStatus.UNAVAILABLE
    response = create_appointment(client, auth_headers, future_start)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "TIME_SLOT_UNAVAILABLE"


def test_appointment_detail_hides_other_customers_resource(client, auth_headers, future_start):
    created = create_appointment(client, auth_headers, future_start).get_json()["data"]
    assert register(client, email="other@example.com").status_code == 201
    other_tokens = login(client, email="other@example.com").get_json()["data"]
    other_headers = {"Authorization": f"Bearer {other_tokens['access_token']}"}

    response = client.get(f"/api/appointments/{created['id']}", headers=other_headers)
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "APPOINTMENT_NOT_FOUND"


def test_list_returns_only_current_customer_appointments(client, auth_headers, future_start):
    create_appointment(client, auth_headers, future_start)
    assert register(client, email="other@example.com").status_code == 201
    other_tokens = login(client, email="other@example.com").get_json()["data"]
    other_headers = {"Authorization": f"Bearer {other_tokens['access_token']}"}
    create_appointment(client, other_headers, future_start + timedelta(hours=1))

    response = client.get("/api/appointments/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()["data"]["total"] == 1


def test_cancel_preserves_history_and_rejects_duplicate(client, auth_headers, future_start):
    created = create_appointment(client, auth_headers, future_start).get_json()["data"]
    url = f"/api/appointments/{created['id']}/cancel"

    first = client.patch(url, headers=auth_headers)
    second = client.patch(url, headers=auth_headers)

    assert first.status_code == 200
    assert first.get_json()["data"]["status"] == "cancelled"
    assert second.status_code == 409


def test_reschedule_checks_availability_and_excludes_current_appointment(
    client, auth_headers, availability, future_start
):
    created = create_appointment(client, auth_headers, future_start).get_json()["data"]
    new_start = future_start + timedelta(days=1)
    response = client.patch(
        f"/api/appointments/{created['id']}/reschedule",
        headers=auth_headers,
        json={"start_at": new_start.isoformat()},
    )

    assert response.status_code == 200
    assert availability.calls[-1]["exclude_appointment_id"] == created["id"]


def test_reschedule_rejects_unavailable_slot(client, auth_headers, availability, future_start):
    created = create_appointment(client, auth_headers, future_start).get_json()["data"]
    availability.status = AvailabilityStatus.UNAVAILABLE
    response = client.patch(
        f"/api/appointments/{created['id']}/reschedule",
        headers=auth_headers,
        json={"start_at": (future_start + timedelta(days=1)).isoformat()},
    )
    assert response.status_code == 409


def test_database_constraint_prevents_same_active_start_double_booking(
    client, auth_headers, future_start
):
    assert create_appointment(client, auth_headers, future_start).status_code == 201
    assert register(client, email="other@example.com").status_code == 201
    other_tokens = login(client, email="other@example.com").get_json()["data"]
    other_headers = {"Authorization": f"Bearer {other_tokens['access_token']}"}

    collision = create_appointment(client, other_headers, future_start)
    assert collision.status_code == 409
    assert collision.get_json()["error"]["code"] == "TIME_SLOT_UNAVAILABLE"


def test_failed_availability_check_rolls_back(client, auth_headers, app, future_start):
    class BrokenGateway:
        def check(self, **kwargs):
            raise RuntimeError("dependency failed")

    app.extensions["availability_gateway"] = BrokenGateway()
    response = create_appointment(client, auth_headers, future_start)
    assert response.status_code == 500

    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Appointment.id))) == 0


def test_past_or_naive_datetime_is_rejected(client, auth_headers, future_start):
    past = client.post(
        "/api/appointments",
        headers=auth_headers,
        json={**appointment_payload(future_start), "start_at": "2020-01-01T10:00:00Z"},
    )
    naive = client.post(
        "/api/appointments",
        headers=auth_headers,
        json={**appointment_payload(future_start), "start_at": "2030-01-01T10:00:00"},
    )
    assert past.status_code == 422
    assert naive.status_code == 422
