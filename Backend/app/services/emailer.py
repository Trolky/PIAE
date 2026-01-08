from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """SMTP email sender.

    Args:
        host: SMTP hostname. Defaults to config.
        port: SMTP port. Defaults to config.
        mail_from: From-address. Defaults to config.
    """

    def __init__(self, *, host: str | None = None, port: int | None = None, mail_from: str | None = None) -> None:
        """Initialize the email service."""
        self._host = host or settings.smtp_host
        self._port = port or settings.smtp_port
        self._from = mail_from or settings.smtp_from

    def send(self, *, to: str, subject: str, text: str) -> None:
        """Send a plaintext email.

        Args:
            to: Recipient email.
            subject: Email subject.
            text: Email body.
        """
        msg = EmailMessage()
        msg["From"] = self._from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text)

        logger.info(
            "Sending email",
            extra={"smtp_host": self._host, "smtp_port": self._port, "to": to, "subject": subject},
        )

        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            smtp.send_message(msg)
