"""Input guardrail: strips high-risk PII from raw CV text before any agent sees it.

Keeps name/email (needed for applications); removes national IDs, bank
details, and card numbers.
"""
import re

_PATTERNS: list[tuple[re.Pattern, str]] = [
    # IBAN (e.g. DE89 3704 0044 0532 0130 00)
    (re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,8}(?:\s?[A-Z0-9]{1,4})?\b"), "[REDACTED-IBAN]"),
    # Payment card numbers (13-19 digits, optionally spaced/dashed)
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[REDACTED-CARD]"),
    # US SSN
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED-SSN]"),
    # Pakistani CNIC (e.g. 12345-1234567-1)
    (re.compile(r"\b\d{5}-\d{7}-\d\b"), "[REDACTED-NATIONAL-ID]"),
    # Generic 'passport no' / 'national id' followed by value
    (
        re.compile(r"(?i)\b(passport|national\s*id|cnic|ssn)\s*(no\.?|number|#)?\s*[:\-]?\s*[A-Z0-9\-]{6,20}"),
        "[REDACTED-ID]",
    ),
]


def scrub_pii(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
