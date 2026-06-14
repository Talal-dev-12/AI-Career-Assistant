"""Output guardrail: reject resume formatting that breaks ATS parsers.

Resumes are produced as Markdown; anything implying images, tables/columns,
or embedded HTML is rejected.
"""
import re

_FORBIDDEN: list[tuple[re.Pattern, str]] = [
    (re.compile(r"!\[[^\]]*\]\("), "embedded image"),
    (re.compile(r"^\s*\|.+\|\s*$", re.M), "table/column layout"),
    (re.compile(r"<(img|table|div|style|font)\b", re.I), "embedded HTML"),
    (re.compile(r"[\u2502\u2551]"), "box-drawing column characters"),
]


def validate_ats(resume_markdown: str) -> list[str]:
    """Return list of violations (empty == ATS-safe)."""
    return [label for pattern, label in _FORBIDDEN if pattern.search(resume_markdown)]
