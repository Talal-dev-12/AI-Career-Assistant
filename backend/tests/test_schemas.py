import pytest
from pydantic import ValidationError

from app.models.schemas import (
    ApplicationStatus,
    JobListing,
    JobSource,
    MatchScore,
    UserProfile,
)


def test_job_listing_roundtrip():
    job = JobListing(
        external_id="greenhouse:acme:1",
        source=JobSource.GREENHOUSE,
        title="Backend Engineer",
        company="acme",
        url="https://example.com/1",
    )
    assert JobListing.model_validate(job.model_dump()) == job


def test_match_score_bounds():
    with pytest.raises(ValidationError):
        MatchScore(job_external_id="x", user_id="u", score=101)


def test_profile_defaults():
    p = UserProfile(user_id="u1", full_name="Ada", email="ada@example.com")
    assert p.profile_version == 1 and p.skills == []


def test_status_values():
    assert ApplicationStatus.AWAITING_USER_APPROVAL.value == "awaiting_user_approval"
