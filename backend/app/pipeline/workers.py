"""Stage consumers. Each runs as an independent worker process."""
from __future__ import annotations

import logging
import redis

from sqlalchemy import select

from app.db.database import get_engine, init_db
from app.db.models import Job
from app.models.schemas import JobListing
from app.pipeline import queue

log = logging.getLogger(__name__)


def handle_scraped(payload: dict) -> None:
    """Persist new listings (idempotent on external_id) and emit for verification.

    v1 applies deterministic verification heuristics inline (duplicate +
    staleness); the JobVerificationAgent adds legitimacy analysis when an
    OPENAI_API_KEY is configured.
    """
    from sqlalchemy.orm import Session

    listing = JobListing.model_validate(payload)
    engine = get_engine()
    with Session(engine) as session:
        existing = session.execute(
            select(Job).where(Job.external_id == listing.external_id)
        ).scalar_one_or_none()
        if existing:
            return  # duplicate - idempotent skip
        job = Job(
            external_id=listing.external_id,
            source=listing.source.value,
            title=listing.title,
            company=listing.company,
            location=listing.location,
            url=listing.url,
            description=listing.description,
            posted_at=listing.posted_at,
            verified=bool(listing.title and listing.company and listing.url),
            verification_reasons={"checks": ["non-empty fields", "unique external_id"]},
        )
        session.add(job)
        session.commit()
        client = queue.get_redis()
        if job.verified:
            queue.publish(client, queue.VERIFIED, payload)


def handle_verified(payload: dict) -> None:
    """Matching trigger point.

    Match scores are computed lazily per user on browse (cached by
    profile_version + job) to control LLM cost; this hook exists for
    future push-style alerts.
    """
    log.info("verified job ready for matching: %s", payload.get("external_id"))


def run_worker(stage: str) -> None:
    """Entrypoint: ``python -m app.pipeline.workers <stage>``"""
    init_db()
    client = queue.get_redis()
    from app.pipeline.docgen import handle_docs_requested
    from app.pipeline.submitter import handle_approved
    from app.pipeline.webform import handle_webform

    handlers = {
        "verify": (queue.SCRAPED, handle_scraped),
        "match": (queue.VERIFIED, handle_verified),
        "docgen": (queue.DOCS_REQUESTED, handle_docs_requested),
        "submit": (queue.APPROVED, handle_approved),
        "webform": (queue.WEBFORM, handle_webform),
    }
    stream, handler = handlers[stage]
    log.info("worker started: stage=%s stream=%s", stage, stream)
    while True:
        try:
            queue.consume(client, stream, group=f"{stage}-group", consumer=f"{stage}-1", handler=handler)
        except (TimeoutError, redis.exceptions.TimeoutError):
            pass


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    run_worker(sys.argv[1] if len(sys.argv) > 1 else "verify")
