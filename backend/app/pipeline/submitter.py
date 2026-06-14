"""Submission worker: consumes ``apps.approved``.

Email submission embeds a ``[REF:xxxxxxxx]`` token in the subject so the
Application Tracking Agent can deterministically match inbound replies.
Board-hosted jobs (Greenhouse/Lever web forms) are recorded as pending until
the Phase 4 browser-automation worker lands - status honestly stays APPROVED.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_engine
from app.db.models import Application, ApplicationEvent, Job
from app.models.schemas import ApplicationStatus
from app.services.email import send_application_email_raw

log = logging.getLogger(__name__)


def handle_approved(payload: dict) -> None:
    engine = get_engine()
    with Session(engine) as session:
        application = session.get(Application, payload["application_id"])
        if application is None or application.status != ApplicationStatus.APPROVED.value:
            return  # idempotent
        job = session.get(Job, application.job_id)
        contact_email = payload.get("contact_email")

        if contact_email and get_settings().smtp_host:
            ref = f"REF:{application.id[:8]}"
            result = send_application_email_raw(
                contact_email,
                subject=f"Application: {job.title} [{ref}]",
                body=application.cover_letter_markdown or "",
                resume_markdown=application.resume_markdown or "",
            )
            if not result.get("sent"):
                raise RuntimeError(result.get("reason", "email submission failed"))
            application.status = ApplicationStatus.SUBMITTED.value
            application.submitted_at = datetime.utcnow()
            application.confirmation_ref = ref
            session.add(
                ApplicationEvent(
                    application_id=application.id,
                    event="submitted_via_email",
                    detail={"to": contact_email, "ref": ref},
                )
            )
            log.info("application %s submitted via email", application.id)
        else:
            from app.pipeline import queue

            queue.publish(
                queue.get_redis(),
                queue.WEBFORM,
                {"application_id": application.id},
            )
            session.add(
                ApplicationEvent(
                    application_id=application.id,
                    event="submission_routed_to_webform",
                    detail={"apply_url": job.url},
                )
            )
            log.info("application %s routed to web-form worker: %s", application.id, job.url)
        session.commit()
