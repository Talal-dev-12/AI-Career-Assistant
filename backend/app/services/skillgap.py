"""Skill-gap learning roadmaps aggregated from cached match scores."""
from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MatchScoreRow, Profile
from app.models.schemas import LearningRoadmap, LearningRoadmapItem

RESOURCE_CATALOG: dict[str, list[str]] = {
    "python": [
        "https://docs.python.org/3/tutorial/",
        "https://www.freecodecamp.org/learn/scientific-computing-with-python/",
    ],
    "sql": ["https://sqlbolt.com/", "https://www.postgresql.org/docs/current/tutorial.html"],
    "docker": ["https://docs.docker.com/get-started/"],
    "kubernetes": ["https://kubernetes.io/docs/tutorials/kubernetes-basics/"],
    "aws": ["https://aws.amazon.com/training/digital/"],
    "react": ["https://react.dev/learn"],
    "typescript": ["https://www.typescriptlang.org/docs/handbook/intro.html"],
    "fastapi": ["https://fastapi.tiangolo.com/tutorial/"],
    "machine learning": ["https://developers.google.com/machine-learning/crash-course"],
    "deep learning": ["https://www.fast.ai/"],
    "llm": ["https://platform.openai.com/docs/guides/agents"],
    "ci/cd": ["https://docs.gitlab.com/ee/ci/quick_start/"],
    "git": ["https://git-scm.com/book/en/v2"],
    "testing": ["https://docs.pytest.org/en/stable/getting-started.html"],
}

ESTIMATED_WEEKS = {"kubernetes": 4, "aws": 4, "machine learning": 6, "deep learning": 6}
DEFAULT_WEEKS = 2
MAX_ITEMS = 10


def fallback_resources(skill: str) -> list[str]:
    query = skill.replace(" ", "+")
    return [
        f"https://www.freecodecamp.org/news/search/?query={query}",
        f"https://www.coursera.org/search?query={query}",
    ]


def roadmap_from_missing_counts(
    user_id: str, target_role: str, counts: Counter[str]
) -> LearningRoadmap:
    items: list[LearningRoadmapItem] = []
    if counts:
        top = counts.most_common(MAX_ITEMS)
        max_count = top[0][1]
        for skill, count in top:
            # frequency drives priority: most-demanded gap = 1 (highest)
            priority = max(1, min(5, 1 + round(4 * (1 - count / max_count))))
            items.append(
                LearningRoadmapItem(
                    skill=skill,
                    priority=priority,
                    resources=RESOURCE_CATALOG.get(skill, fallback_resources(skill)),
                    estimated_weeks=ESTIMATED_WEEKS.get(skill, DEFAULT_WEEKS),
                )
            )
    return LearningRoadmap(user_id=user_id, target_role=target_role, items=items)


def build_roadmap(db: Session, user_id: str, target_role: str | None = None) -> LearningRoadmap:
    profile = db.execute(
        select(Profile).where(Profile.user_id == user_id)
    ).scalar_one_or_none()
    if profile is None:
        raise LookupError("profile not found")
    if not target_role:
        roles = (profile.data or {}).get("target_roles", [])
        target_role = roles[0] if roles else "general"

    rows = db.execute(
        select(MatchScoreRow).where(
            MatchScoreRow.user_id == user_id,
            MatchScoreRow.profile_version == profile.version,  # only current-profile scores
        )
    ).scalars().all()
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update((row.detail or {}).get("missing_skills", []))
    return roadmap_from_missing_counts(user_id, target_role, counts)
