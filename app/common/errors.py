from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from flask import Flask, Response, jsonify
from flask_limiter.errors import RateLimitExceeded
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from app.config.extensions import db

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class APIError(Exception):
    code: str
    message: str
    status_code: int
    details: Any | None = None


class AuthenticationError(APIError):
    def __init__(self, message: str = "Credenciais inválidas.") -> None:
        super().__init__("INVALID_CREDENTIALS", message, 401)


class NotFoundError(APIError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 404)


class ConflictError(APIError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 409)


class IntegrationUnavailableError(APIError):
    def __init__(self, integration: str) -> None:
        super().__init__(
            "INTEGRATION_UNAVAILABLE",
            f"A integração {integration} está temporariamente indisponível.",
            503,
        )


def _error_response(error: APIError) -> tuple[Response, int]:
    payload: dict[str, Any] = {"error": {"code": error.code, "message": error.message}}
    if error.details is not None:
        payload["error"]["details"] = error.details
    return jsonify(payload), error.status_code


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)
    def handle_api_error(error: APIError) -> tuple[Response, int]:
        db.session.rollback()
        return _error_response(error)

    @app.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError) -> tuple[Response, int]:
        db.session.rollback()
        return _error_response(
            APIError("VALIDATION_ERROR", "Os dados enviados são inválidos.", 422, error.messages)
        )

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(error: RateLimitExceeded) -> tuple[Response, int]:
        return _error_response(
            APIError("RATE_LIMIT_EXCEEDED", "Muitas tentativas. Tente novamente mais tarde.", 429)
        )

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(error: IntegrityError) -> tuple[Response, int]:
        db.session.rollback()
        logger.warning("database_integrity_error")
        return _error_response(
            APIError("DATABASE_CONFLICT", "A operação conflita com dados existentes.", 409)
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException) -> tuple[Response, int]:
        code = error.name.upper().replace(" ", "_")
        return _error_response(APIError(code, error.description, error.code or 500))

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception) -> tuple[Response, int]:
        db.session.rollback()
        logger.exception("unhandled_api_error", exc_info=error)
        return _error_response(APIError("INTERNAL_SERVER_ERROR", "Ocorreu um erro interno.", 500))
