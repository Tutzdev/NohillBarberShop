import re

from marshmallow import (
    RAISE,
    Schema,
    ValidationError,
    fields,
    pre_load,
    validate,
    validates,
)

PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{9,14}$")


class EmailNormalizationMixin:
    @pre_load
    def normalize_email(self, data: dict, **kwargs) -> dict:
        if isinstance(data, dict) and isinstance(data.get("email"), str):
            return {**data, "email": data["email"].strip().lower()}
        return data


class RegisterSchema(EmailNormalizationMixin, Schema):
    class Meta:
        unknown = RAISE

    name = fields.String(required=True, validate=validate.Length(min=2, max=120))
    email = fields.Email(required=True)
    phone = fields.String(required=True)
    password = fields.String(
        required=True, load_only=True, validate=validate.Length(min=10, max=128)
    )

    @validates("phone")
    def validate_phone(self, value: str, **kwargs) -> None:
        normalized = re.sub(r"[\s()-]", "", value)
        if not PHONE_PATTERN.fullmatch(normalized):
            raise ValidationError("Informe um telefone válido com DDD.")

    @pre_load
    def normalize_fields(self, data: dict, **kwargs) -> dict:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if isinstance(normalized.get("name"), str):
            normalized["name"] = " ".join(normalized["name"].split())
        if isinstance(normalized.get("phone"), str):
            normalized["phone"] = re.sub(r"[\s()-]", "", normalized["phone"])
        return normalized


class LoginSchema(EmailNormalizationMixin, Schema):
    class Meta:
        unknown = RAISE

    email = fields.Email(required=True)
    password = fields.String(
        required=True, load_only=True, validate=validate.Length(min=1, max=128)
    )


class ChangePasswordSchema(Schema):
    class Meta:
        unknown = RAISE

    current_password = fields.String(
        required=True, load_only=True, validate=validate.Length(min=1, max=128)
    )
    new_password = fields.String(
        required=True, load_only=True, validate=validate.Length(min=10, max=128)
    )


class ForgotPasswordSchema(EmailNormalizationMixin, Schema):
    class Meta:
        unknown = RAISE

    email = fields.Email(required=True)


class ResetPasswordSchema(Schema):
    class Meta:
        unknown = RAISE

    token = fields.String(required=True, load_only=True, validate=validate.Length(min=32, max=256))
    new_password = fields.String(
        required=True, load_only=True, validate=validate.Length(min=10, max=128)
    )
