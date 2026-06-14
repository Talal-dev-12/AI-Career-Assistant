"""SMTP submission service (shared by the agent tool and the submit worker)."""
import smtplib
from email.message import EmailMessage

from app.config import get_settings


def send_application_email_raw(
    to_address: str, subject: str, body: str, resume_markdown: str
) -> dict:
    settings = get_settings()
    if not settings.smtp_host:
        return {"sent": False, "reason": "SMTP not configured (set SMTP_* env vars)"}
    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_attachment(
        resume_markdown.encode(), maintype="text", subtype="markdown", filename="resume.md"
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
    return {"sent": True}
