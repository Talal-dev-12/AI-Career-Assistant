from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from mabd.database.db import get_session
from mabd.models.models import InterviewSession, InterviewStartRequest, AnswerSubmitRequest, InterviewSessionRead
from mabd.services.interview_service import (
    start_interview_session, 
    submit_interview_response, 
    evaluate_interview_session
)

router = APIRouter(tags=["Mock Interview Prep"])

@router.post("/interview/start", response_model=InterviewSessionRead, status_code=201)
def start_interview(request: InterviewStartRequest, session: Session = Depends(get_session)):
    return start_interview_session(
        session=session,
        user_id=request.user_id,
        job_id=request.job_id
    )

# Commented out duplicate endpoint; handled by multiplexer in app.api.main
# @router.post("/interview/{session_id}/answer", response_model=InterviewSession)
# def submit_answer(session_id: str, request: AnswerSubmitRequest, session: Session = Depends(get_session)):
#     return submit_interview_response(
#         session=session,
#         session_id=session_id,
#         question_index=request.question_index,
#         answer=request.answer
#     )

@router.post("/interview/{session_id}/evaluate", response_model=InterviewSessionRead)
def evaluate_interview(session_id: str, session: Session = Depends(get_session)):
    return evaluate_interview_session(
        session=session,
        session_id=session_id
    )

# Commented out duplicate endpoint; handled by multiplexer in app.api.main
# @router.get("/interview/{session_id}", response_model=InterviewSession)
# def get_interview_session(session_id: str, session: Session = Depends(get_session)):
#     db_session = session.get(InterviewSession, session_id)
#     if not db_session:
#         raise HTTPException(status_code=404, detail="Interview session not found")
#     return db_session