"""Web-form submission worker: consumes ``apps.webform`` (Phase 4).

Instead of brittle browser automation, this worker submits through the
providers' official application endpoints:

- Greenhouse Job Board API (POST, Basic auth with a Job Board API key)
- Lever Postings API (POST with an API key)

Safety: ``WEBFORM_DRY_RUN`` defaults to true - submissions are fully
prepared and recorded but never sent until the operator flips the flag and
configures provider API keys. Jobs hosted on unsupported providers are
parked with a ``manual_submission_required`` event carrying the apply URL.
"""
from __future__ import annotations

import logging
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_engine
from app.db.models import Application, ApplicationEvent, Job, User
from app.models.schemas import ApplicationStatus

log = logging.getLogger(__name__)

GREENHOUSE_APPLY = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
LEVER_APPLY = "https://api.lever.co/v0/postings/{company}/{posting_id}"


def parse_external_id(external_id: str) -> tuple[str, str, str] | None:
    """``greenhouse:board:123`` -> (provider, account, posting_id)."""
    parts = external_id.split(":", 2)
    if len(parts) != 3 or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


def build_submission(
    provider: str,
    account: str,
    posting_id: str,
    *,
    full_name: str,
    email: str,
    resume_markdown: str,
    cover_letter: str,
) -> dict | None:
    """Build the endpoint + form fields for a provider, or None if unsupported."""
    first, _, last = full_name.partition(" ")
    if provider == "greenhouse":
        return {
            "url": GREENHOUSE_APPLY.format(board=account, job_id=posting_id),
            "fields": {
                "first_name": first,
                "last_name": last or "-",
                "email": email,
                "cover_letter_text": cover_letter,
                "resume_text": resume_markdown,
            },
            "auth_setting": "greenhouse_job_board_api_key",
        }
    if provider == "lever":
        return {
            "url": LEVER_APPLY.format(company=account, posting_id=posting_id),
            "fields": {
                "name": full_name,
                "email": email,
                "comments": cover_letter,
                "resume_text": resume_markdown,
            },
            "auth_setting": "lever_postings_api_key",
        }
    return None


def _post(submission: dict, provider: str, api_key: str) -> httpx.Response:
    if provider == "greenhouse":
        return httpx.post(
            submission["url"], data=submission["fields"], auth=(api_key, ""), timeout=30
        )
    return httpx.post(
        submission["url"], params={"key": api_key}, data=submission["fields"], timeout=30
    )


def handle_webform(payload: dict) -> None:
    settings = get_settings()
    engine = get_engine()
    with Session(engine) as session:
        application = session.get(Application, payload["application_id"])
        if application is None or application.status != ApplicationStatus.APPROVED.value:
            return  # idempotent
        job = session.get(Job, application.job_id)
        user = session.get(User, application.user_id)

        parsed = parse_external_id(job.external_id)
        submission = (
            build_submission(
                *parsed,
                full_name=user.full_name,
                email=user.email,
                resume_markdown=application.resume_markdown or "",
                cover_letter=application.cover_letter_markdown or "",
            )
            if parsed
            else None
        )
        if submission is None:
            session.add(
                ApplicationEvent(
                    application_id=application.id,
                    event="manual_submission_required",
                    detail={"apply_url": job.url, "reason": "unsupported provider"},
                )
            )
            session.commit()
            log.info("application %s requires manual submission: %s", application.id, job.url)
            return

        provider = parsed[0]
        api_key = getattr(settings, submission["auth_setting"], "")
        if settings.webform_dry_run or not api_key:
            session.add(
                ApplicationEvent(
                    application_id=application.id,
                    event="webform_submission_prepared",
                    detail={
                        "provider": provider,
                        "endpoint": submission["url"],
                        "dry_run": settings.webform_dry_run,
                        "has_api_key": bool(api_key),
                    },
                )
            )
            session.commit()
            log.info("webform submission prepared (not sent) for %s", application.id)
            return

        response = _post(submission, provider, api_key)
        if response.status_code >= 400:
            session.add(
                ApplicationEvent(
                    application_id=application.id,
                    event="webform_submission_failed",
                    detail={"status": response.status_code, "body": response.text[:500]},
                )
            )
            session.commit()
            raise RuntimeError(  # queue retries, then dead-letters
                f"webform submission failed: HTTP {response.status_code}"
            )

        application.status = ApplicationStatus.SUBMITTED.value
        application.submitted_at = datetime.utcnow()
        application.confirmation_ref = f"{provider}:{parsed[2]}"
        session.add(
            ApplicationEvent(
                application_id=application.id,
                event="submitted_via_webform",
                detail={"provider": provider, "endpoint": submission["url"]},
            )
        )
        session.commit()
        log.info("application %s submitted via %s web form", application.id, provider)
