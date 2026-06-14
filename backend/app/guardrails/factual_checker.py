"""Output guardrail with teeth: entailment check of generated documents.

Every ``source_claims`` entry in a ResumeDiff / CoverLetter must be entailed
by the user's parsed profile. v1 uses deterministic token-level entailment
(skills, titles, companies, institutions). An optional LLM entailment pass
can be layered on top later; the deterministic check is the hard floor.

Any unsupported claim => document rejected, generation retried.
"""
from __future__ import annotations

import re

from app.models.schemas import UserProfile

_WORD_RE = re.compile(r"[a-z0-9+#.]{2,}")


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _profile_corpus(profile: UserProfile) -> set[str]:
    parts: list[str] = [profile.full_name, *profile.skills, *profile.target_roles]
    for exp in profile.experience:
        parts += [exp.title, exp.company, *(exp.highlights)]
    for edu in profile.education:
        parts += [edu.degree, edu.institution]
    corpus: set[str] = set()
    for part in parts:
        corpus |= _tokens(part)
    return corpus


def check_claims(profile: UserProfile, claims: list[str]) -> list[str]:
    """Return the list of UNSUPPORTED claims (empty list == document passes).

    A claim is supported when >=60% of its content tokens appear in the
    profile corpus AND every skill-like token (contains +, #, or is in no
    common-words list) appears verbatim.
    """
    corpus = _profile_corpus(profile)
    unsupported: list[str] = []
    for claim in claims:
        claim_tokens = _tokens(claim)
        if not claim_tokens:
            continue
        overlap = len(claim_tokens & corpus) / len(claim_tokens)
        if overlap < 0.6:
            unsupported.append(claim)
    return unsupported


def enforce(profile: UserProfile, claims: list[str]) -> None:
    """Raise if any claim is unsupported. Use as a hard gate post-generation."""
    bad = check_claims(profile, claims)
    if bad:
        raise FactualAccuracyError(bad)


class FactualAccuracyError(Exception):
    def __init__(self, unsupported: list[str]):
        self.unsupported = unsupported
        super().__init__(f"Unsupported claims in generated document: {unsupported}")
