from tests.conftest import login, register


def test_customer_can_read_own_profile(client, customer_account, auth_headers):
    response = client.get("/api/customers/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.get_json()["data"]["id"] == customer_account["id"]


def test_customer_can_update_allowed_fields(client, auth_headers):
    response = client.patch(
        "/api/customers/me",
        headers=auth_headers,
        json={"name": "Nicolas Atualizado", "phone": "+5511888888888"},
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["name"] == "Nicolas Atualizado"


def test_customer_cannot_mass_assign_protected_fields(client, auth_headers):
    response = client.patch(
        "/api/customers/me",
        headers=auth_headers,
        json={"password_hash": "attacker-controlled", "id": 999},
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_customer_update_rejects_invalid_fields(client, auth_headers):
    response = client.patch("/api/customers/me", headers=auth_headers, json={"phone": "invalid"})
    assert response.status_code == 422


def test_customer_update_rejects_duplicate_email(client, auth_headers):
    assert register(client, email="other@example.com").status_code == 201
    response = client.patch(
        "/api/customers/me",
        headers=auth_headers,
        json={"email": "other@example.com"},
    )

    assert response.status_code == 409
    assert login(client).status_code == 200
