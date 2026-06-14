from app.models.schemas import MatchScore
from app.services import llm


def _match() -> MatchScore:
    return MatchScore(job_external_id="e", user_id="u", score=50.0, rationale="heuristic")


def test_refine_match_falls_back_without_llm(monkeypatch):
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: None)
    assert llm.refine_match(_match(), "t", "d", {}) == _match()


def test_refine_match_blends_valid_llm_score(monkeypatch):
    monkeypatch.setattr(
        llm, "complete_json", lambda *a, **k: {"score": 90, "rationale": "strong fit"}
    )
    refined = llm.refine_match(_match(), "t", "d", {})
    assert refined.score == 70.0
    assert "strong fit" in refined.rationale


def test_refine_match_rejects_out_of_range_score(monkeypatch):
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: {"score": 500})
    assert llm.refine_match(_match(), "t", "d", {}).score == 50.0


def test_refine_feedback_falls_back_without_llm(monkeypatch):
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: None)
    assert llm.refine_feedback("q", "a", "r", 6.0, "fb") == (6.0, "fb")


def test_refine_feedback_blends_valid_llm_result(monkeypatch):
    monkeypatch.setattr(
        llm, "complete_json", lambda *a, **k: {"score": 8, "feedback": "Solid answer."}
    )
    assert llm.refine_feedback("q", "a", "r", 6.0, "fb") == (7.0, "Solid answer.")
