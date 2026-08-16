from __future__ import annotations

from datetime import timedelta

import pytest

from app import create_app
from app.common.time import utc_now
from app.config.extensions import db
from app.integrations.availability import AvailabilityDecision, AvailabilityStatus


class FakeAvailabilityGateway:
    def __init__(self) -> None:
        self.status = AvailabilityStatus.AVAILABLE
        self.duration = timedelta(minutes=30)
        self.calls: list[dict] = []

    def check(self, **kwargs) -> AvailabilityDecision:
        self.calls.append(kwargs)
        end_at = (
            kwargs["start_at"] + self.duration
            if self.status == AvailabilityStatus.AVAILABLE
            else None
        )
        return AvailabilityDecision(self.status, end_at)


class CapturingPasswordResetNotifier:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def send(self, *, recipient: str, token: str) -> None:
        self.messages.append({"recipient": recipient, "token": token})


@pytest.fixture
def app():
    application = create_app(
        "testing",
        overrides={
            "SECRET_KEY": "test-secret-at-least-thirty-two-characters",
            "JWT_SECRET_KEY": "test-jwt-secret-at-least-thirty-two-characters",
        },
    )
    gateway = FakeAvailabilityGateway()
    notifier = CapturingPasswordResetNotifier()
    application.extensions["availability_gateway"] = gateway
    application.extensions["password_reset_notifier"] = notifier

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def availability(app) -> FakeAvailabilityGateway:
    return app.extensions["availability_gateway"]


@pytest.fixture
def password_notifier(app) -> CapturingPasswordResetNotifier:
    return app.extensions["password_reset_notifier"]


def register(client, *, email: str = "nicolas@example.com", password: str = "senha-segura-123"):
    return client.post(
        "/api/auth/register",
        json={
            "name": "Nicolas Silva",
            "email": email,
            "phone": "+5511999999999",
            "password": password,
        },
    )


def login(client, *, email: str = "nicolas@example.com", password: str = "senha-segura-123"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


@pytest.fixture
def customer_account(client):
    response = register(client)
    assert response.status_code == 201
    return response.get_json()["data"]


@pytest.fixture
def tokens(client, customer_account):
    response = login(client)
    assert response.status_code == 200
    return response.get_json()["data"]


@pytest.fixture
def auth_headers(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def future_start():
    return utc_now() + timedelta(days=2)
