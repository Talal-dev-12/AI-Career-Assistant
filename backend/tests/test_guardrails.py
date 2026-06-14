import pytest

from app.guardrails.ats_validator import validate_ats
from app.guardrails.factual_checker import FactualAccuracyError, check_claims, enforce
from app.guardrails.pii_scrubber import scrub_pii
from app.models.schemas import ExperienceEntry, UserProfile


def _profile() -> UserProfile:
    return UserProfile(
        user_id="u1",
        full_name="Ada Lovelace",
        email="ada@example.com",
        skills=["python", "fastapi", "postgresql"],
        experience=[
            ExperienceEntry(
                title="Backend Engineer",
                company="Acme",
                highlights=["built python fastapi services"],
            )
        ],
    )


def test_pii_scrubber_removes_ids():
    text = "CNIC: 12345-1234567-1 and SSN 123-45-6789 and IBAN DE89370400440532013000"
    clean = scrub_pii(text)
    assert "12345-1234567-1" not in clean
    assert "123-45-6789" not in clean
    assert "DE89" not in clean


def test_pii_scrubber_keeps_normal_text():
    assert "python developer" in scrub_pii("Experienced python developer")


def test_factual_checker_accepts_supported_claims():
    assert check_claims(_profile(), ["Backend Engineer at Acme", "python fastapi"]) == []


def test_factual_checker_rejects_invented_claims():
    bad = check_claims(_profile(), ["Kubernetes administrator certification from Google"])
    assert bad, "invented claim must be flagged"
    with pytest.raises(FactualAccuracyError):
        enforce(_profile(), bad)


def test_ats_validator_flags_tables_and_images():
    assert validate_ats("![logo](x.png)\n| a | b |") != []


def test_ats_validator_passes_clean_markdown():
    assert validate_ats("# Ada Lovelace\n## Experience\n- Built APIs") == []
