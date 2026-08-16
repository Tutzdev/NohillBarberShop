from datetime import timedelta

from flask_jwt_extended import create_access_token

from app.auth.models import AuthSession, PasswordResetToken
from app.common.time import utc_now
from app.config.extensions import db
from app.customers.models import Customer
from tests.conftest import login, register


def test_register_valid_customer(client, app):
    response = register(client)

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["email"] == "nicolas@example.com"
    assert "password" not in data
    with app.app_context():
        customer = db.session.scalar(db.select(Customer))
        assert customer.password_hash != "senha-segura-123"
        assert customer.password_hash.startswith("$argon2id$")


def test_register_rejects_duplicate_email(client):
    assert register(client).status_code == 201
    response = register(client, password="outra-senha-segura")

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


def test_register_rejects_unknown_or_invalid_fields(client):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "N",
            "email": "invalid",
            "phone": "123",
            "password": "short",
            "admin": True,
        },
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_returns_token_pair(client, customer_account):
    response = login(client)

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["access_token"]
    assert data["refresh_token"]


def test_login_does_not_reveal_whether_account_exists(client, customer_account):
    wrong_password = login(client, password="senha-incorreta")
    missing_account = login(client, email="missing@example.com", password="senha-incorreta")

    assert wrong_password.status_code == missing_account.status_code == 401
    assert wrong_password.get_json() == missing_account.get_json()


def test_protected_route_requires_authentication(client):
    response = client.get("/api/customers/me")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_logout_revokes_whole_session(client, tokens, auth_headers):
    response = client.post("/api/auth/logout", headers=auth_headers)

    assert response.status_code == 204
    assert client.get("/api/customers/me", headers=auth_headers).status_code == 401
    refresh_response = client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert refresh_response.status_code == 401
    assert refresh_response.get_json()["error"]["code"] == "TOKEN_REVOKED"


def test_refresh_rotates_refresh_token(client, tokens):
    original = tokens["refresh_token"]
    response = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {original}"})

    assert response.status_code == 200
    assert response.get_json()["data"]["refresh_token"] != original
    replay = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {original}"})
    assert replay.status_code == 401


def test_expired_token_is_rejected(client, app, customer_account):
    with app.app_context():
        session = AuthSession(
            customer_id=customer_account["id"],
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(days=1),
        )
        db.session.add(session)
        db.session.commit()
        token = create_access_token(
            identity=str(customer_account["id"]),
            additional_claims={"sid": session.id},
            expires_delta=timedelta(seconds=-1),
        )

    response = client.get("/api/customers/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "TOKEN_EXPIRED"


def test_password_reset_is_neutral_and_one_time(client, customer_account, password_notifier, app):
    existing = client.post("/api/auth/forgot-password", json={"email": "nicolas@example.com"})
    missing = client.post("/api/auth/forgot-password", json={"email": "missing@example.com"})
    assert existing.status_code == missing.status_code == 200
    assert existing.get_json() == missing.get_json()
    raw_token = password_notifier.messages[0]["token"]

    with app.app_context():
        stored = db.session.scalar(db.select(PasswordResetToken))
        assert stored.token_hash != raw_token

    reset = client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "new_password": "nova-senha-segura"},
    )
    assert reset.status_code == 204
    assert login(client, password="nova-senha-segura").status_code == 200
    assert (
        client.post(
            "/api/auth/reset-password",
            json={"token": raw_token, "new_password": "terceira-senha-segura"},
        ).status_code
        == 401
    )


def test_password_reset_does_not_reveal_delivery_failure(client, customer_account, app):
    class FailingNotifier:
        def send(self, **kwargs):
            raise ConnectionError("must not reach the API response")

    app.extensions["password_reset_notifier"] = FailingNotifier()
    response = client.post("/api/auth/forgot-password", json={"email": "nicolas@example.com"})

    assert response.status_code == 200
    assert "Se a conta existir" in response.get_json()["data"]["message"]


def test_change_password_revokes_sessions(client, auth_headers):
    response = client.post(
        "/api/auth/change-password",
        headers=auth_headers,
        json={
            "current_password": "senha-segura-123",
            "new_password": "senha-nova-segura",
        },
    )

    assert response.status_code == 204
    assert client.get("/api/customers/me", headers=auth_headers).status_code == 401
    assert login(client, password="senha-nova-segura").status_code == 200
