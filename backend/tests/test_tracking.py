from app.models.schemas import ApplicationStatus
from app.pipeline.tracking import classify_reply, extract_ref


def test_extract_ref():
    assert extract_ref("Re: Application: Python Engineer [REF:a1b2c3d4]") == "a1b2c3d4"
    assert extract_ref("no token here") is None


def test_classify_interview():
    status = classify_reply("Next steps", "We'd like to schedule a call to discuss your fit")
    assert status == ApplicationStatus.INTERVIEW.value


def test_classify_rejection():
    status = classify_reply(
        "Your application", "Unfortunately we decided to move forward with other candidates"
    )
    assert status == ApplicationStatus.REJECTED_BY_COMPANY.value


def test_classify_offer_takes_precedence_over_interview():
    status = classify_reply("Good news", "We are pleased to offer you the role after the interview")
    assert status == ApplicationStatus.OFFER.value


def test_classify_unknown_returns_none():
    assert classify_reply("FYI", "Thanks, we received your application") is None
