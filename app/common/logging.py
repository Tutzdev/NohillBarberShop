from __future__ import annotations

import logging
import re
import time
from uuid import uuid4

from flask import Flask, g, request

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


def configure_logging(app: Flask) -> None:
    level = logging.DEBUG if app.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def register_request_logging(app: Flask) -> None:
    logger = logging.getLogger("nohill.requests")

    @app.before_request
    def start_request() -> None:
        supplied_id = request.headers.get("X-Request-ID", "")
        g.request_id = supplied_id if REQUEST_ID_PATTERN.fullmatch(supplied_id) else str(uuid4())
        g.request_started_at = time.monotonic()

    @app.after_request
    def finish_request(response):
        duration_ms = round((time.monotonic() - g.request_started_at) * 1000, 2)
        response.headers["X-Request-ID"] = g.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not app.debug:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        logger.info(
            "request_completed method=%s path=%s status=%s duration_ms=%s request_id=%s",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            g.request_id,
        )
        return response
