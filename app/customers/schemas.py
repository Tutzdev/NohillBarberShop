import re

from marshmallow import RAISE, Schema, ValidationError, fields, pre_load, validate, validates

from app.auth.schemas import PHONE_PATTERN


class UpdateCustomerSchema(Schema):
    class Meta:
        unknown = RAISE

    name = fields.String(validate=validate.Length(min=2, max=120))
    email = fields.Email()
    phone = fields.String()

    @pre_load
    def normalize_fields(self, data: dict, **kwargs) -> dict:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if isinstance(normalized.get("name"), str):
            normalized["name"] = " ".join(normalized["name"].split())
        if isinstance(normalized.get("email"), str):
            normalized["email"] = normalized["email"].strip().lower()
        if isinstance(normalized.get("phone"), str):
            normalized["phone"] = re.sub(r"[\s()-]", "", normalized["phone"])
        return normalized

    @validates("phone")
    def validate_phone(self, value: str, **kwargs) -> None:
        if not PHONE_PATTERN.fullmatch(value):
            raise ValidationError("Informe um telefone válido com DDD.")
