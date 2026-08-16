from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime

from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token, decode_token
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.auth.models import AuthSession, PasswordResetToken
from app.auth.passwords import hash_password, needs_rehash, verify_password
from app.common.errors import AuthenticationError, ConflictError
from app.common.time import ensure_utc, utc_now
from app.config.extensions import db
from app.customers.models import Customer
from app.integrations.password_reset import get_password_reset_notifier

_DUMMY_PASSWORD_HASH = hash_password("dummy-password-never-used")
logger = logging.getLogger(__name__)


def register_customer(*, name: str, email: str, phone: str, password: str) -> Customer:
    if db.session.scalar(db.select(Customer).where(Customer.email == email)):
        raise ConflictError("EMAIL_ALREADY_REGISTERED", "Já existe uma conta com este e-mail.")

    customer = Customer(
        name=name,
        email=email,
        phone=phone,
        password_hash=hash_password(password),
    )
    db.session.add(customer)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ConflictError(
            "EMAIL_ALREADY_REGISTERED", "Já existe uma conta com este e-mail."
        ) from exc
    return customer


def login(*, email: str, password: str) -> tuple[Customer, dict[str, str]]:
    customer = db.session.scalar(db.select(Customer).where(Customer.email == email))
    password_hash = customer.password_hash if customer else _DUMMY_PASSWORD_HASH
    if not verify_password(password_hash, password) or customer is None:
        raise AuthenticationError()

    if needs_rehash(customer.password_hash):
        customer.password_hash = hash_password(password)

    session = AuthSession(
        customer_id=customer.id,
        created_at=utc_now(),
        expires_at=utc_now() + current_app.config["JWT_REFRESH_TOKEN_EXPIRES"],
    )
    db.session.add(session)
    db.session.flush()
    tokens = _create_token_pair(customer, session)
    db.session.commit()
    return customer, tokens


def rotate_tokens(
    customer: Customer, session: AuthSession, *, presented_jti: str
) -> dict[str, str]:
    tokens, new_jti, expires_at = _build_token_pair(customer, session)
    rotated = db.session.execute(
        update(AuthSession)
        .where(
            AuthSession.id == session.id,
            AuthSession.current_refresh_jti == presented_jti,
            AuthSession.revoked_at.is_(None),
        )
        .values(current_refresh_jti=new_jti, expires_at=expires_at)
    )
    if rotated.rowcount != 1:
        db.session.rollback()
        raise AuthenticationError("O refresh token já foi utilizado ou revogado.")
    db.session.commit()
    return tokens


def _create_token_pair(customer: Customer, session: AuthSession) -> dict[str, str]:
    tokens, refresh_jti, expires_at = _build_token_pair(customer, session)
    session.current_refresh_jti = refresh_jti
    session.expires_at = expires_at
    return tokens


def _build_token_pair(
    customer: Customer, session: AuthSession
) -> tuple[dict[str, str], str, datetime]:
    claims = {"sid": session.id}
    identity = str(customer.id)
    access_token = create_access_token(identity=identity, additional_claims=claims)
    refresh_token = create_refresh_token(identity=identity, additional_claims=claims)
    refresh_payload = decode_token(refresh_token)
    expires_at = datetime.fromtimestamp(refresh_payload["exp"], UTC)
    tokens = {"access_token": access_token, "refresh_token": refresh_token}
    return tokens, refresh_payload["jti"], expires_at


def revoke_session(session: AuthSession) -> None:
    if session.revoked_at is None:
        session.revoked_at = utc_now()
        db.session.commit()


def change_password(customer: Customer, *, current_password: str, new_password: str) -> None:
    if not verify_password(customer.password_hash, current_password):
        raise AuthenticationError("A senha atual está incorreta.")
    if verify_password(customer.password_hash, new_password):
        raise ConflictError("PASSWORD_UNCHANGED", "A nova senha deve ser diferente da atual.")

    customer.password_hash = hash_password(new_password)
    _revoke_all_sessions(customer.id)
    db.session.commit()


def request_password_reset(email: str) -> None:
    customer = db.session.scalar(db.select(Customer).where(Customer.email == email))
    if customer is None:
        verify_password(_DUMMY_PASSWORD_HASH, "constant-time-enumeration-protection")
        return

    now = utc_now()
    for old_token in customer.password_reset_tokens:
        if old_token.used_at is None:
            old_token.used_at = now

    raw_token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        customer_id=customer.id,
        token_hash=_token_hash(raw_token),
        expires_at=now + current_app.config["PASSWORD_RESET_EXPIRES"],
    )
    db.session.add(reset_token)
    db.session.commit()
    try:
        get_password_reset_notifier().send(recipient=customer.email, token=raw_token)
    except Exception as exc:  # Integration errors must not enable account enumeration.
        logger.error("password_reset_delivery_failed error_type=%s", type(exc).__name__)


def reset_password(*, raw_token: str, new_password: str) -> None:
    token = db.session.scalar(
        db.select(PasswordResetToken).where(PasswordResetToken.token_hash == _token_hash(raw_token))
    )
    if token is None or token.used_at is not None or ensure_utc(token.expires_at) <= utc_now():
        raise AuthenticationError("O token de redefinição é inválido ou expirou.")

    consumed = db.session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.id == token.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=utc_now())
    )
    if consumed.rowcount != 1:
        db.session.rollback()
        raise AuthenticationError("O token de redefinição é inválido ou expirou.")

    customer = db.session.get(Customer, token.customer_id)
    customer.password_hash = hash_password(new_password)
    _revoke_all_sessions(customer.id)
    db.session.commit()


def _revoke_all_sessions(customer_id: int) -> None:
    db.session.execute(
        update(AuthSession)
        .where(AuthSession.customer_id == customer_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )


def _token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
