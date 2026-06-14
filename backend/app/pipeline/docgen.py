"""Document-generation worker: consumes ``docs.requested``.

Flow per application:
1. Load user profile + job.
2. Generate ResumeDiff + CoverLetter via LLM agents; when no OPENAI_API_KEY
   is configured, fall back to a deterministic builder that only reorganizes
   profile facts (fully factual by construction).
3. Hard gates: factual-accuracy entailment check + ATS validator. On failure
   the guardrail feedback is fed back into a regeneration attempt; persistent
   failure raises so the queue retries and eventually dead-letters.
4. Persist documents and move the application to AWAITING_USER_APPROVAL.
"""
from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_engine
from app.db.models import Application, ApplicationEvent, Job, Profile, User
from app.guardrails.ats_validator import validate_ats
from app.guardrails.factual_checker import check_claims
from app.models.schemas import ApplicationStatus, CoverLetter, ResumeDiff, UserProfile

log = logging.getLogger(__name__)

MAX_GENERATION_ATTEMPTS = 2


def _load_profile(session: Session, user_id: str) -> UserProfile:
    user = session.get(User, user_id)
    row = session.execute(
        select(Profile).where(Profile.user_id == user_id)
    ).scalar_one_or_none()
    if row and row.data:
        return UserProfile.model_validate(row.data)
    return UserProfile(user_id=user_id, full_name=user.full_name, email=user.email)


def build_fallback_documents(profile: UserProfile, job) -> tuple[ResumeDiff, CoverLetter]:
    """Deterministic, fully-factual documents (no LLM): reorder profile facts
    so skills mentioned in the job description come first."""
    matched = [s for s in profile.skills if s.lower() in job.description.lower()]
    ordered = matched + [s for s in profile.skills if s not in matched]

    lines = [f"# {profile.full_name}", str(profile.email), "", "## Skills"]
    lines += [f"- {s}" for s in ordered] or ["- (no skills extracted yet)"]
    lines += ["", "## Experience"]
    for exp in profile.experience:
        lines.append(f"### {exp.title} - {exp.company}")
        lines += [f"- {h}" for h in exp.highlights]
    lines += ["", "## Education"]
    for edu in profile.education:
        lines.append(f"- {edu.degree}, {edu.institution}")

    resume = ResumeDiff(
        job_external_id=job.external_id,
        resume_markdown="\n".join(lines),
        highlighted_skills=matched,
        source_claims=[
            *profile.skills,
            *(f"{e.title} {e.company}" for e in profile.experience),
        ],
    )
    cover = CoverLetter(
        job_external_id=job.external_id,
        body_markdown=(
            f"Dear {job.company} team,\n\n"
            f"I am applying for the {job.title} role. My background includes "
            f"{', '.join(ordered[:5]) or 'the experience detailed in my resume'}, "
            f"which aligns with the requirements in your posting.\n\n"
            f"Best regards,\n{profile.full_name}"
        ),
        source_claims=ordered[:5],
    )
    return resume, cover


async def generate_with_agents(
    profile: UserProfile, job, feedback: list[str]
) -> tuple[ResumeDiff, CoverLetter]:
    from agents import Runner

    from app.agents.definitions import cover_letter_agent, resume_agent

    job_block = json.dumps(
        {"title": job.title, "company": job.company, "description": job.description[:6000]}
    )
    note = (
        "\n\nPREVIOUS ATTEMPT REJECTED by the factual-accuracy guardrail. "
        "Remove or rephrase: " + "; ".join(feedback)
        if feedback
        else ""
    )
    prompt = f"PROFILE:\n{profile.model_dump_json()}\n\nJOB:\n{job_block}{note}"
    resume_res = await Runner.run(resume_agent, input=prompt)
    cover_res = await Runner.run(cover_letter_agent, input=prompt)
    return resume_res.final_output, cover_res.final_output


def validate_documents(
    profile: UserProfile, resume: ResumeDiff, cover: CoverLetter
) -> list[str]:
    """Hard gates. Empty list == both documents pass."""
    problems: list[str] = []
    problems += [
        f"resume claim not supported: {c}" for c in check_claims(profile, resume.source_claims)
    ]
    problems += [
        f"cover-letter claim not supported: {c}"
        for c in check_claims(profile, cover.source_claims)
    ]
    problems += [f"ATS violation: {v}" for v in validate_ats(resume.resume_markdown)]
    return problems


def handle_docs_requested(payload: dict) -> None:
    engine = get_engine()
    with Session(engine) as session:
        application = session.get(Application, payload["application_id"])
        if application is None or application.status != ApplicationStatus.DRAFT.value:
            return  # idempotent: already processed or rejected
        job = session.get(Job, application.job_id)
        profile = _load_profile(session, application.user_id)

        problems: list[str] = []
        resume = cover = None
        for _attempt in range(MAX_GENERATION_ATTEMPTS):
            if get_settings().openai_api_key:
                resume, cover = asyncio.run(generate_with_agents(profile, job, problems))
            else:
                resume, cover = build_fallback_documents(profile, job)
            problems = validate_documents(profile, resume, cover)
            if not problems:
                break

        if problems:
            session.add(
                ApplicationEvent(
                    application_id=application.id,
                    event="documents_rejected_by_guardrail",
                    detail={"problems": problems},
                )
            )
            session.commit()
            raise RuntimeError(f"document generation failed guardrails: {problems}")

        application.resume_markdown = resume.resume_markdown
        application.cover_letter_markdown = cover.body_markdown
        application.status = ApplicationStatus.AWAITING_USER_APPROVAL.value
        session.add(ApplicationEvent(application_id=application.id, event="documents_ready"))
        session.commit()
        log.info("documents ready for application %s", application.id)
