from flask import Blueprint, request
from flask_jwt_extended import get_jwt, jwt_required

from app.auth.jwt_callbacks import get_current_customer
from app.auth.models import AuthSession
from app.auth.schemas import (
    ChangePasswordSchema,
    ForgotPasswordSchema,
    LoginSchema,
    RegisterSchema,
    ResetPasswordSchema,
)
from app.auth.service import (
    change_password,
    login,
    register_customer,
    request_password_reset,
    reset_password,
    revoke_session,
    rotate_tokens,
)
from app.common.responses import no_content, success
from app.common.schemas import load_json
from app.config.extensions import db, limiter
from app.customers.serialization import serialize_customer

blueprint = Blueprint("auth", __name__)


@blueprint.post("/register")
@limiter.limit("5 per minute")
def register():
    data = load_json(request, RegisterSchema())
    customer = register_customer(**data)
    return success(serialize_customer(customer), 201)


@blueprint.post("/login")
@limiter.limit("5 per minute")
def authenticate():
    data = load_json(request, LoginSchema())
    customer, tokens = login(**data)
    return success({"customer": serialize_customer(customer), **tokens})


@blueprint.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    customer = get_current_customer()
    claims = get_jwt()
    session = db.session.get(AuthSession, claims["sid"])
    return success(rotate_tokens(customer, session, presented_jti=claims["jti"]))


@blueprint.post("/logout")
@jwt_required(verify_type=False)
def logout():
    session = db.session.get(AuthSession, get_jwt()["sid"])
    revoke_session(session)
    return no_content()


@blueprint.post("/change-password")
@jwt_required()
@limiter.limit("5 per hour")
def update_password():
    data = load_json(request, ChangePasswordSchema())
    change_password(get_current_customer(), **data)
    return no_content()


@blueprint.post("/forgot-password")
@limiter.limit("3 per hour")
def forgot_password():
    data = load_json(request, ForgotPasswordSchema())
    request_password_reset(data["email"])
    return success({"message": "Se a conta existir, enviaremos as instruções de redefinição."})


@blueprint.post("/reset-password")
@limiter.limit("5 per hour")
def apply_password_reset():
    data = load_json(request, ResetPasswordSchema())
    reset_password(raw_token=data["token"], new_password=data["new_password"])
    return no_content()
