from app.pipeline.webform import build_submission, parse_external_id


def test_parse_external_id():
    assert parse_external_id("greenhouse:acme:123") == ("greenhouse", "acme", "123")
    assert parse_external_id("malformed") is None
    assert parse_external_id("greenhouse::123") is None


def test_greenhouse_submission_payload():
    submission = build_submission(
        "greenhouse",
        "acme",
        "123",
        full_name="Ada Lovelace",
        email="ada@example.com",
        resume_markdown="# Ada",
        cover_letter="Dear team",
    )
    assert submission["url"] == "https://boards-api.greenhouse.io/v1/boards/acme/jobs/123"
    assert submission["fields"]["first_name"] == "Ada"
    assert submission["fields"]["last_name"] == "Lovelace"
    assert submission["auth_setting"] == "greenhouse_job_board_api_key"


def test_lever_submission_payload():
    submission = build_submission(
        "lever",
        "acme",
        "abc-123",
        full_name="Ada Lovelace",
        email="ada@example.com",
        resume_markdown="# Ada",
        cover_letter="Dear team",
    )
    assert submission["url"] == "https://api.lever.co/v0/postings/acme/abc-123"
    assert submission["fields"]["name"] == "Ada Lovelace"
    assert submission["auth_setting"] == "lever_postings_api_key"


def test_unsupported_provider_returns_none():
    assert (
        build_submission(
            "aggregator",
            "x",
            "1",
            full_name="A B",
            email="a@b.com",
            resume_markdown="",
            cover_letter="",
        )
        is None
    )
