"""Application Tracking Agent: parses inbound reply emails, updates statuses.

Outgoing application emails embed a ``[REF:xxxxxxxx]`` token in the subject;
replies quoting it are matched deterministically to an application. Replies
are classified (interview / offer / rejection) with keyword heuristics - an
LLM classification pass can be layered on top later. An interview detection
is the trigger point for the SkillGapInterviewAgent.
"""
from __future__ import annotations

import email
import imaplib
import logging
import re
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_engine, init_db
from app.db.models import Application, ApplicationEvent
from app.models.schemas import ApplicationStatus

log = logging.getLogger(__name__)

REF_RE = re.compile(r"REF:([0-9a-f]{8})", re.I)

_OFFER = re.compile(r"\b(offer letter|pleased to offer|extend an offer)\b", re.I)
_INTERVIEW = re.compile(
    r"\b(interview|screening call|next round|schedule a (call|chat)|availability)\b", re.I
)
_REJECTION = re.compile(
    r"\b(unfortunately|not (be )?moving forward|other candidates"
    r"|decided to (proceed|move forward) with|regret to inform)\b",
    re.I,
)


def classify_reply(subject: str, body: str) -> str | None:
    """Return the new ApplicationStatus value, or None when inconclusive."""
    text = f"{subject}\n{body}"
    if _OFFER.search(text):
        return ApplicationStatus.OFFER.value
    if _INTERVIEW.search(text):
        return ApplicationStatus.INTERVIEW.value
    if _REJECTION.search(text):
        return ApplicationStatus.REJECTED_BY_COMPANY.value
    return None


def extract_ref(text: str) -> str | None:
    match = REF_RE.search(text)
    return match.group(1).lower() if match else None


def apply_inbound_email(session: Session, subject: str, body: str) -> bool:
    """Match a reply to an application and update its status. True if matched."""
    ref = extract_ref(f"{subject}\n{body}")
    if not ref:
        return False
    application = session.execute(
        select(Application).where(Application.confirmation_ref == f"REF:{ref}")
    ).scalar_one_or_none()
    if application is None:
        return False

    new_status = classify_reply(subject, body)
    detail = {"subject": subject[:200], "classified": new_status}
    if new_status and application.status != new_status:
        application.status = new_status
        session.add(
            ApplicationEvent(
                application_id=application.id, event=f"status_{new_status}", detail=detail
            )
        )
        if new_status == ApplicationStatus.INTERVIEW.value:
            # Trigger point for SkillGapInterviewAgent mock-interview prep.
            log.info("interview detected for application %s", application.id)
    else:
        session.add(
            ApplicationEvent(
                application_id=application.id, event="reply_received", detail=detail
            )
        )
    return True


def _message_text(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                return payload.decode(errors="replace") if payload else ""
        return ""
    payload = msg.get_payload(decode=True)
    return payload.decode(errors="replace") if payload else ""


def poll_inbox() -> int:
    settings = get_settings()
    if not settings.imap_host:
        return 0  # tracking disabled until IMAP_* env vars are set
    handled = 0
    with imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port) as imap:
        imap.login(settings.imap_user, settings.imap_password)
        imap.select("INBOX")
        _, data = imap.search(None, "UNSEEN")
        engine = get_engine()
        for num in (data[0] or b"").split():
            _, msg_data = imap.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            with Session(engine) as session:
                if apply_inbound_email(session, msg.get("Subject", ""), _message_text(msg)):
                    session.commit()
                    handled += 1
    return handled


def main() -> None:
    init_db()
    interval = get_settings().tracking_poll_seconds
    log.info("tracking agent started (poll every %ss)", interval)
    while True:
        try:
            handled = poll_inbox()
            if handled:
                log.info("processed %d inbound replies", handled)
        except Exception:
            log.exception("tracking poll failed")
        time.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
