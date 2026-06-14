from types import SimpleNamespace

from app.models.schemas import ExperienceEntry, UserProfile
from app.pipeline.docgen import build_fallback_documents, validate_documents


def _profile() -> UserProfile:
    return UserProfile(
        user_id="u1",
        full_name="Ada Lovelace",
        email="ada@example.com",
        skills=["python", "fastapi", "sql"],
        experience=[
            ExperienceEntry(
                title="Backend Engineer",
                company="Acme",
                highlights=["shipped python services"],
            )
        ],
    )


def _job():
    return SimpleNamespace(
        external_id="greenhouse:acme:1",
        title="Python Engineer",
        company="acme",
        description="We need python and sql experience",
        url="https://example.com/1",
    )


def test_fallback_documents_are_factual_and_ats_safe():
    profile = _profile()
    resume, cover = build_fallback_documents(profile, _job())
    assert validate_documents(profile, resume, cover) == []
    assert resume.highlighted_skills == ["python", "sql"]
    assert "Ada Lovelace" in resume.resume_markdown
    assert "Python Engineer" in cover.body_markdown


def test_matched_skills_are_reordered_first():
    resume, _ = build_fallback_documents(_profile(), _job())
    skills_section = resume.resume_markdown.split("## Skills")[1]
    assert skills_section.index("python") < skills_section.index("fastapi")


def test_validate_documents_catches_invented_claims():
    profile = _profile()
    resume, cover = build_fallback_documents(profile, _job())
    resume.source_claims.append("Certified Kubernetes administrator at Google")
    problems = validate_documents(profile, resume, cover)
    assert any("not supported" in p for p in problems)


def test_validate_documents_catches_ats_violations():
    profile = _profile()
    resume, cover = build_fallback_documents(profile, _job())
    resume.resume_markdown += "\n| col1 | col2 |"
    problems = validate_documents(profile, resume, cover)
    assert any("ATS violation" in p for p in problems)
