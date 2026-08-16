from __future__ import annotations

from flask import Request
from marshmallow import Schema, ValidationError


def load_json(request: Request, schema: Schema) -> dict:
    if not request.is_json:
        raise ValidationError({"_schema": ["Content-Type deve ser application/json."]})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError({"_schema": ["O corpo deve ser um objeto JSON."]})
    return schema.load(payload)
