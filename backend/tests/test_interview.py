from app.services.interview import (
    DEFAULT_QUESTIONS,
    QUESTION_BANK,
    questions_for_role,
    score_answer,
)

STAR_ANSWER = (
    "During my internship at a fintech startup, our checkout service kept timing out. "
    "My goal was to find the root cause, so I was responsible for profiling the API. "
    "I implemented request tracing and I designed a caching layer with Redis, "
    "which led to a result of latency reduced by 40% and improved conversion for 10000 users. "
    "The outcome taught me to measure before optimizing."
)


def test_star_answer_outscores_shallow_answer():
    question = "Tell me about a time you debugged a production incident."
    star_score, _ = score_answer(question, STAR_ANSWER, "software engineer")
    shallow_score, shallow_feedback = score_answer(
        question, "I fixed a bug once.", "software engineer"
    )
    assert star_score > shallow_score
    assert "Situation" in shallow_feedback


def test_quantified_impact_adds_bonus():
    base = (
        "During the project my goal was clear so i implemented the fix "
        "and the result improved things."
    )
    quantified = base + " Latency dropped by 40%."
    question = "Describe a challenge you faced."
    assert (
        score_answer(question, quantified, "engineer")[0]
        > score_answer(question, base, "engineer")[0]
    )


def test_unknown_role_falls_back_to_default_questions():
    assert questions_for_role("Astronaut Chef") == DEFAULT_QUESTIONS
    assert questions_for_role("Senior Software Engineer") == QUESTION_BANK["software engineer"]
