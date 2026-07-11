"""Outbound email with a pluggable delivery seam.

If SMTP is configured (settings.SMTP_HOST), messages go out over SMTP. Otherwise
the message is logged — which is exactly what local/dev wants, since the
verification link is also surfaced in the register/resend response in dev.
"""
import smtplib
from email.message import EmailMessage

from config import settings
from logger import logger


def _send_smtp(to_email: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_STARTTLS:
            server.starttls()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)


def send_email(to_email: str, subject: str, body: str) -> None:
    if settings.SMTP_HOST:
        try:
            _send_smtp(to_email, subject, body)
            logger.info("email.sent", extra={"to": to_email, "subject": subject})
        except Exception:
            logger.exception("email.send_failed", extra={"to": to_email})
            raise
    else:
        # Dev fallback: no SMTP configured — log so the link is still reachable.
        logger.info(f"[email:dev] to={to_email} subject={subject!r}\n{body}")


def send_verification_email(to_email: str, verification_url: str) -> None:
    send_email(
        to_email,
        subject="Verify your email — Research Factory",
        body=(
            "Welcome to Research Factory!\n\n"
            "Confirm your email address by opening this link:\n\n"
            f"{verification_url}\n\n"
            "This link expires in 24 hours. If you didn't create an account, ignore this email."
        ),
    )
