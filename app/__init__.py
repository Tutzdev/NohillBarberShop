from __future__ import annotations

from flask import Flask

from app.common.errors import register_error_handlers
from app.common.logging import configure_logging, register_request_logging
from app.config.extensions import cors, db, jwt, limiter, migrate
from app.config.settings import get_config


def create_app(config_name: str | None = None, *, overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    if overrides:
        app.config.update(overrides)

    config_class.validate(app.config)
    configure_logging(app)
    _initialize_extensions(app)
    _register_blueprints(app)
    register_error_handlers(app)
    register_request_logging(app)

    return app


def _initialize_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    from app import models  # noqa: F401
    from app.auth import jwt_callbacks  # noqa: F401


def _register_blueprints(app: Flask) -> None:
    from app.appointments.routes import blueprint as appointments_blueprint
    from app.auth.routes import blueprint as auth_blueprint
    from app.customers.routes import blueprint as customers_blueprint
    from app.health.routes import blueprint as health_blueprint

    app.register_blueprint(auth_blueprint, url_prefix="/api/auth")
    app.register_blueprint(customers_blueprint, url_prefix="/api/customers")
    app.register_blueprint(appointments_blueprint, url_prefix="/api/appointments")
    app.register_blueprint(health_blueprint, url_prefix="/api")
