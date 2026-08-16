from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _origins_from_environment() -> list[str]:
    value = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in value.split(",") if origin.strip()]


class BaseConfig:
    ENV_NAME = "base"
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-secret-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "development-only-jwt-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///nohill.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "15")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv("REFRESH_TOKEN_DAYS", "7")))
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_ERROR_MESSAGE_KEY = "message"
    CORS_ORIGINS = _origins_from_environment()
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    PASSWORD_RESET_EXPIRES = timedelta(minutes=int(os.getenv("PASSWORD_RESET_MINUTES", "30")))
    PASSWORD_RESET_URL = os.getenv("PASSWORD_RESET_URL", "http://localhost:3000/reset-password")
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    JSON_SORT_KEYS = False
    MAX_CONTENT_LENGTH = 64 * 1024

    @classmethod
    def validate(cls, config: Mapping[str, Any]) -> None:
        if not config["CORS_ORIGINS"]:
            raise RuntimeError("CORS_ORIGINS must contain at least one allowed origin")
        if len(config["SECRET_KEY"]) < 32:
            raise RuntimeError("SECRET_KEY must contain at least 32 characters")
        if len(config["JWT_SECRET_KEY"]) < 32:
            raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters")


class DevelopmentConfig(BaseConfig):
    ENV_NAME = "development"
    DEBUG = True


class TestingConfig(BaseConfig):
    ENV_NAME = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite+pysqlite:///:memory:"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    RATELIMIT_ENABLED = False


class ProductionConfig(BaseConfig):
    ENV_NAME = "production"
    DEBUG = False

    @classmethod
    def validate(cls, config: Mapping[str, Any]) -> None:
        super().validate(config)
        required = {
            "SECRET_KEY": config.get("SECRET_KEY"),
            "JWT_SECRET_KEY": config.get("JWT_SECRET_KEY"),
            "DATABASE_URL": os.getenv("DATABASE_URL"),
            "RATELIMIT_STORAGE_URI": os.getenv("RATELIMIT_STORAGE_URI"),
            "PASSWORD_RESET_URL": os.getenv("PASSWORD_RESET_URL"),
            "SMTP_HOST": os.getenv("SMTP_HOST"),
            "SMTP_USERNAME": os.getenv("SMTP_USERNAME"),
            "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD"),
            "SMTP_FROM_EMAIL": os.getenv("SMTP_FROM_EMAIL"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"Missing required production settings: {', '.join(missing)}")
        if config["SECRET_KEY"] == "development-only-secret-change-me":
            raise RuntimeError("SECRET_KEY must be changed in production")
        if config["JWT_SECRET_KEY"] == "development-only-jwt-secret-change-me":
            raise RuntimeError("JWT_SECRET_KEY must be changed in production")
        if "*" in config["CORS_ORIGINS"]:
            raise RuntimeError("Wildcard CORS origin is not allowed in production")
        if config["RATELIMIT_STORAGE_URI"] == "memory://":
            raise RuntimeError("A shared rate-limit storage is required in production")
        if not str(config["SQLALCHEMY_DATABASE_URI"]).startswith(
            ("postgresql://", "postgresql+psycopg://")
        ):
            raise RuntimeError(
                "Production requires PostgreSQL for transactional appointment locking"
            )


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(config_name: str | None = None) -> type[BaseConfig]:
    name = config_name or os.getenv("FLASK_ENV", "development")
    try:
        return CONFIGS[name]
    except KeyError as exc:
        choices = ", ".join(CONFIGS)
        raise RuntimeError(f"Unknown environment {name!r}. Expected one of: {choices}") from exc
