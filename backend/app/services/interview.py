"""Heuristic AI mock-interview engine (no API key required).

Role-templated question banks + scoring that rewards STAR structure, depth,
quantified impact, and role relevance.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import InterviewSession, InterviewTurn
from app.services.matching import extract_skills

QUESTION_BANK: dict[str, list[str]] = {
    "software engineer": [
        "Walk me through a project you designed end to end. What trade-offs did you make?",
        "Tell me about a time you debugged a production incident. What was the root cause?",
        "How do you ensure code quality in a team setting?",
        "Describe a time you disagreed with a technical decision. How did you handle it?",
        "What is the most complex system you have scaled, and what broke first?",
    ],
    "data scientist": [
        "Describe a model you took from prototype to production. What changed along the way?",
        "Tell me about a time your analysis contradicted stakeholder expectations.",
        "How do you handle missing or imbalanced data?",
        "Walk me through how you validate that a model is actually working in production.",
        "Describe a project where feature engineering made the biggest difference.",
    ],
    "product manager": [
        "Tell me about a product decision you made with incomplete data.",
        "How do you prioritize a backlog when everything is urgent?",
        "Describe a launch that did not go as planned. What did you do?",
        "How do you balance user needs against business goals?",
        "Tell me about a time you had to say no to a stakeholder.",
    ],
}

DEFAULT_QUESTIONS = [
    "Tell me about yourself and what draws you to this role.",
    "Describe a challenge you faced recently and how you overcame it.",
    "Tell me about a time you worked under a tight deadline.",
    "What accomplishment are you most proud of, and why?",
    "Where do you want to grow in the next two years?",
]

STAR_MARKERS: dict[str, tuple[str, ...]] = {
    "situation": ("situation", "when i", "while i", "at my", "during", "we were"),
    "task": ("task", "goal", "responsible", "needed to", "had to", "my job was"),
    "action": (
        "action", "i built", "i designed", "i implemented", "i led", "i created",
        "so i", "i decided",
    ),
    "result": (
        "result", "outcome", "led to", "improved", "reduced", "increased",
        "achieved", "learned",
    ),
}

_QUANTIFIED_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|percent|x\b|ms\b|users|requests|hours|days|weeks)?", re.I
)


def questions_for_role(role: str) -> list[str]:
    key = role.strip().lower()
    for bank_role, questions in QUESTION_BANK.items():
        if bank_role in key or key in bank_role:
            return questions
    return DEFAULT_QUESTIONS


def score_answer(question: str, answer: str, role: str) -> tuple[float, str]:
    text = answer.strip()
    if not text:
        return 0.0, "No answer provided."
    lower = text.lower()
    score = 2.0
    notes: list[str] = []

    star_hits = sum(1 for markers in STAR_MARKERS.values() if any(m in lower for m in markers))
    score += star_hits  # up to +4
    if star_hits >= 3:
        notes.append("Clear STAR structure.")
    else:
        notes.append("Structure your answer as Situation, Task, Action, Result.")

    words = len(text.split())
    if words >= 120:
        score += 2.0
        notes.append("Good depth.")
    elif words >= 50:
        score += 1.0
    else:
        notes.append("Add more detail and a concrete example.")

    if _QUANTIFIED_RE.search(text):
        score += 1.0
        notes.append("Quantified impact strengthens the answer.")
    else:
        notes.append("Quantify your impact with numbers (%, time saved, users).")

    if extract_skills(text) & extract_skills(f"{question} {role}"):
        score += 1.0
        notes.append("Relevant to the target role.")

    return min(10.0, round(score, 1)), " ".join(notes)


def start_session(db: Session, user_id: str, role: str) -> tuple[InterviewSession, str]:
    questions = questions_for_role(role)
    session = InterviewSession(user_id=user_id, role=role)
    db.add(session)
    db.flush()
    first_question = questions[0]
    db.add(InterviewTurn(session_id=session.id, question=first_question))
    db.flush()
    return session, first_question


def submit_answer(db: Session, session: InterviewSession, answer: str) -> dict:
    if session.completed:
        raise ValueError("interview already completed")
    questions = questions_for_role(session.role)
    turn = db.execute(
        select(InterviewTurn)
        .where(InterviewTurn.session_id == session.id, InterviewTurn.answer.is_(None))
        .order_by(InterviewTurn.created_at)
    ).scalars().first()
    if turn is None:
        raise ValueError("no open question")

    turn.answer = answer
    heuristic_score, heuristic_feedback = score_answer(turn.question, answer, session.role)
    from app.services.llm import refine_feedback

    turn.score, turn.feedback = refine_feedback(
        turn.question, answer, session.role, heuristic_score, heuristic_feedback
    )
    session.question_index += 1

    next_question: str | None = None
    if session.question_index < len(questions):
        next_question = questions[session.question_index]
        db.add(InterviewTurn(session_id=session.id, question=next_question))
    else:
        session.completed = True
    db.flush()
    return {
        "score": turn.score,
        "feedback": turn.feedback,
        "next_question": next_question,
        "completed": session.completed,
    }
