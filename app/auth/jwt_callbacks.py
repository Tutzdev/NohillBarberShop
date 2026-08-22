from __future__ import annotations

from flask import Response, jsonify
from flask_jwt_extended import current_user

from app.auth.models import AuthSession
from app.common.time import ensure_utc, utc_now
from app.config.extensions import db, jwt
from app.customers.models import Customer


def _jwt_error(code: str, message: str, status: int) -> tuple[Response, int]:
    return jsonify({"error": {"code": code, "message": message}}), status


@jwt.user_identity_loader
def user_identity(customer: Customer | int | str) -> str:
    return str(customer.id if isinstance(customer, Customer) else customer)


@jwt.user_lookup_loader
def load_customer(_header: dict, payload: dict) -> Customer | None:
    try:
        customer_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None
    return db.session.get(Customer, customer_id)


@jwt.token_in_blocklist_loader
def token_is_revoked(_header: dict, payload: dict) -> bool:
    session_id = payload.get("sid")
    if not session_id:
        return True

    session = db.session.get(AuthSession, session_id)

    if session is None or session.revoked_at is not None:
        return True
    if ensure_utc(session.expires_at) <= utc_now():
        return True
    return payload.get("type") == "refresh" and session.current_refresh_jti != payload.get("jti")


@jwt.expired_token_loader
def expired_token(_header: dict, _payload: dict):
    return _jwt_error("TOKEN_EXPIRED", "A autenticação expirou.", 401)


@jwt.invalid_token_loader
def invalid_token(_reason: str):
    return _jwt_error("INVALID_TOKEN", "Token de autenticação inválido.", 401)


@jwt.unauthorized_loader
def missing_token(_reason: str):
    return _jwt_error("AUTHENTICATION_REQUIRED", "Autenticação necessária.", 401)


@jwt.revoked_token_loader
def revoked_token(_header: dict, _payload: dict):
    return _jwt_error("TOKEN_REVOKED", "A sessão não está mais ativa.", 401)


@jwt.user_lookup_error_loader
def missing_user(_header: dict, _payload: dict):
    return _jwt_error("CUSTOMER_NOT_FOUND", "A conta autenticada não existe.", 401)


def get_current_customer() -> Customer:
    return current_user
