"""Function tools for agents.

Tools marked STUB depend on third-party credentials/services and return
structured placeholders until wired; everything else is functional.
"""
from __future__ import annotations

from agents import function_tool

from app.guardrails.pii_scrubber import scrub_pii
from app.services.email import send_application_email_raw


@function_tool
def parse_cv(cv_text: str) -> str:
    """Scrub PII from raw CV text and return the cleaned text for profiling."""
    return scrub_pii(cv_text)


@function_tool
def verify_company(company_name: str) -> dict:
    """Check company legitimacy. STUB: integrate a registry/web lookup.

    Returns a conservative default so unverified companies are flagged,
    not silently approved.
    """
    return {"company": company_name, "registry_checked": False, "flags": []}


@function_tool
def calculate_match_score(profile_skills: list[str], job_description: str) -> dict:
    """Deterministic baseline skill-overlap score (0-100) the agent refines."""
    desc = job_description.lower()
    matched = [s for s in profile_skills if s.lower() in desc]
    score = round(100 * len(matched) / max(len(profile_skills), 1), 1)
    return {"baseline_score": score, "matched_skills": matched}


@function_tool
def send_application_email(
    to_address: str, subject: str, body: str, resume_markdown: str
) -> dict:
    """Send an application email via SMTP with the resume attached as .md."""
    return send_application_email_raw(to_address, subject, body, resume_markdown)


@function_tool
def submit_web_application(job_url: str) -> dict:
    """STUB: browser-automation form submission (Phase 4)."""
    return {"submitted": False, "reason": "web-form automation not yet enabled", "url": job_url}


@function_tool
def generate_learning_roadmap(missing_skills: list[str], target_role: str) -> dict:
    """Seed structure for the roadmap the Skill Gap agent fills with resources."""
    return {
        "target_role": target_role,
        "items": [{"skill": s, "priority": i + 1} for i, s in enumerate(missing_skills[:5])],
    }
