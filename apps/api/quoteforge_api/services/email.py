"""Transactional email via SMTP (§16). We do not build an email service; this is
a thin sender. When SMTP is unconfigured (dev), the message is logged instead.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from quoteforge_api.config import get_settings

logger = logging.getLogger("quoteforge.email")


def send_email(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        logger.info("EMAIL (smtp not configured) to=%s subject=%s\n%s", to, subject, body)
        return
    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_pass)
        server.send_message(msg)


def send_password_reset(to: str, token: str) -> None:
    body = (
        "You requested a password reset for QuoteForge.\n\n"
        f"Use this token to reset your password (valid for 1 hour):\n{token}\n\n"
        "If you did not request this, you can ignore this email."
    )
    send_email(to, "QuoteForge password reset", body)
