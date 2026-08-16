from datetime import timedelta

from app import create_app
from app.common.time import utc_now
from app.config.extensions import db
from tests.conftest import login, register


def test_health_and_security_headers(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Request-ID"]


def test_untrusted_request_id_is_not_reflected(client):
    response = client.get("/api/health", headers={"X-Request-ID": "invalid request id"})
    assert response.headers["X-Request-ID"] != "invalid request id"


def test_unconfigured_availability_fails_closed():
    app = create_app(
        "testing",
        overrides={
            "SECRET_KEY": "test-secret-at-least-thirty-two-characters",
            "JWT_SECRET_KEY": "test-jwt-secret-at-least-thirty-two-characters",
        },
    )
    with app.app_context():
        db.create_all()
    client = app.test_client()
    assert register(client).status_code == 201
    access_token = login(client).get_json()["data"]["access_token"]

    response = client.post(
        "/api/appointments",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "barber_id": 1,
            "service_id": 1,
            "start_at": (utc_now() + timedelta(days=1)).isoformat(),
        },
    )

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "INTEGRATION_UNAVAILABLE"
    with app.app_context():
        db.drop_all()


def test_unknown_route_uses_consistent_error_shape(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"
