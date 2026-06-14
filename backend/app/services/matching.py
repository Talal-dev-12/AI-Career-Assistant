"""Job<->profile compatibility scoring (Roadmap item 3).

Pure heuristics, zero API keys. Scores are cached in ``match_scores`` keyed by
``(user_id, job_id, profile_version)`` so recomputation only happens when the
profile changes. Cached rows also feed the skill-gap roadmap.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, MatchScoreRow, Profile
from app.models.schemas import MatchScore

# Canonical skill -> aliases. Custom word boundaries so "java" never matches
# inside "javascript", and "c++"/"c#" survive punctuation.
SKILL_VOCABULARY: dict[str, tuple[str, ...]] = {
    "python": ("python",),
    "java": ("java",),
    "javascript": ("javascript",),
    "typescript": ("typescript",),
    "react": ("react", "reactjs", "react.js"),
    "vue": ("vue", "vuejs", "vue.js"),
    "node": ("node", "nodejs", "node.js"),
    "fastapi": ("fastapi",),
    "django": ("django",),
    "flask": ("flask",),
    "sql": ("sql", "postgresql", "postgres", "mysql"),
    "nosql": ("mongodb", "nosql", "dynamodb"),
    "redis": ("redis",),
    "docker": ("docker",),
    "kubernetes": ("kubernetes", "k8s"),
    "aws": ("aws", "amazon web services"),
    "gcp": ("gcp", "google cloud"),
    "azure": ("azure",),
    "ci/cd": ("ci/cd", "cicd", "gitlab ci", "github actions", "jenkins"),
    "git": ("git",),
    "machine learning": ("machine learning", "scikit-learn", "sklearn"),
    "deep learning": ("deep learning", "pytorch", "tensorflow"),
    "nlp": ("nlp", "natural language processing"),
    "llm": ("llm", "large language model", "openai", "agents sdk"),
    "data analysis": ("data analysis", "pandas", "numpy"),
    "rest": ("rest", "restful", "rest api"),
    "graphql": ("graphql",),
    "linux": ("linux",),
    "c++": ("c++",),
    "c#": ("c#", ".net"),
    "go": ("golang",),  # bare "go" is too ambiguous
    "rust": ("rust",),
    "selenium": ("selenium", "playwright", "puppeteer"),
    "testing": ("pytest", "unit testing", "tdd"),
    "agile": ("agile", "scrum"),
    "communication": ("communication",),
    "leadership": ("leadership",),
}

_BOUNDARY_BEFORE = r"(?<![A-Za-z0-9+#])"
_BOUNDARY_AFTER = r"(?![A-Za-z0-9+#])"

_PATTERNS: dict[str, re.Pattern[str]] = {
    canonical: re.compile(
        _BOUNDARY_BEFORE + "(?:" + "|".join(re.escape(a) for a in aliases) + ")" + _BOUNDARY_AFTER,
        re.IGNORECASE,
    )
    for canonical, aliases in SKILL_VOCABULARY.items()
}

SKILL_WEIGHT = 70.0
LOCATION_BONUS = 15.0
ROLE_BONUS = 15.0
NEUTRAL_SKILL_SCORE = 35.0  # job text yielded no recognizable skills


def extract_skills(text: str) -> set[str]:
    return {canonical for canonical, pattern in _PATTERNS.items() if pattern.search(text)}


def canonicalize(skills: Iterable[str]) -> set[str]:
    """Map free-form profile skills onto the canonical vocabulary."""
    found: set[str] = set()
    for skill in skills:
        found |= extract_skills(skill)
    return found


def compute_match(
    user_id: str,
    profile_data: dict,
    job_external_id: str,
    title: str,
    description: str,
    location: str | None,
) -> MatchScore:
    required = extract_skills(f"{title}\n{description}")
    have = canonicalize(profile_data.get("skills", []))
    overlap = sorted(required & have)
    missing = sorted(required - have)
    skill_score = (
        SKILL_WEIGHT * len(overlap) / len(required) if required else NEUTRAL_SKILL_SCORE
    )

    location_score = 0.0
    job_location = (location or "").lower()
    user_locations = [loc.lower() for loc in profile_data.get("locations", []) if loc]
    if "remote" in job_location or any(loc in job_location for loc in user_locations):
        location_score = LOCATION_BONUS

    role_score = 0.0
    title_lower = title.lower()
    for role in profile_data.get("target_roles", []):
        tokens = [t for t in re.split(r"\W+", role.lower()) if len(t) > 2]
        if not tokens:
            continue
        if all(t in title_lower for t in tokens):
            role_score = ROLE_BONUS
            break
        if any(t in title_lower for t in tokens):
            role_score = max(role_score, ROLE_BONUS / 2)

    score = round(min(100.0, skill_score + location_score + role_score), 1)
    rationale = (
        f"{len(overlap)}/{len(required)} required skills matched"
        + (", location fit" if location_score else "")
        + (", target-role aligned" if role_score else "")
    )
    return MatchScore(
        job_external_id=job_external_id,
        user_id=user_id,
        score=score,
        skill_overlap=overlap,
        missing_skills=missing,
        rationale=rationale,
    )


def get_or_compute_match(db: Session, user_id: str, job_id: str) -> MatchScoreRow:
    profile = db.execute(
        select(Profile).where(Profile.user_id == user_id)
    ).scalar_one_or_none()
    if profile is None:
        raise LookupError("profile not found")
    job = db.get(Job, job_id)
    if job is None or not job.verified:  # verification gate
        raise LookupError("verified job not found")

    cached = db.execute(
        select(MatchScoreRow).where(
            MatchScoreRow.user_id == user_id,
            MatchScoreRow.job_id == job_id,
            MatchScoreRow.profile_version == profile.version,
        )
    ).scalar_one_or_none()
    if cached:
        return cached

    match = compute_match(
        user_id, profile.data or {}, job.external_id, job.title, job.description, job.location
    )
    from app.services.llm import refine_match

    match = refine_match(match, job.title, job.description, profile.data or {})
    row = MatchScoreRow(
        user_id=user_id,
        job_id=job_id,
        profile_version=profile.version,
        score=match.score,
        detail=match.model_dump(),
    )
    db.add(row)
    db.flush()
    return row
