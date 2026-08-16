from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol
from urllib.parse import urlencode

from flask import current_app

logger = logging.getLogger(__name__)


class PasswordResetNotifier(Protocol):
    def send(self, *, recipient: str, token: str) -> None: ...


class SmtpPasswordResetNotifier:
    def send(self, *, recipient: str, token: str) -> None:
        config = current_app.config
        if not config.get("SMTP_HOST"):
            logger.warning("password_reset_delivery_not_configured")
            return

        query = urlencode({"token": token})
        reset_url = f"{config['PASSWORD_RESET_URL']}?{query}"
        message = EmailMessage()
        message["Subject"] = "Redefinição de senha — Nohill Club"
        message["From"] = config["SMTP_FROM_EMAIL"]
        message["To"] = recipient
        message.set_content(
            "Recebemos uma solicitação para redefinir sua senha. "
            f"Use este link dentro do prazo informado: {reset_url}\n\n"
            "Se você não fez a solicitação, ignore esta mensagem."
        )

        with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"], timeout=10) as smtp:
            if config["SMTP_USE_TLS"]:
                smtp.starttls()
            if config.get("SMTP_USERNAME"):
                smtp.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
            smtp.send_message(message)


def get_password_reset_notifier() -> PasswordResetNotifier:
    notifier = current_app.extensions.get("password_reset_notifier")
    return notifier or SmtpPasswordResetNotifier()
