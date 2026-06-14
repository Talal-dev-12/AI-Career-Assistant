"""FastAPI gateway: profiles, jobs, the human-in-the-loop approval gate, tracking."""
from __future__ import annotations

from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_session, init_db
from app.db.models import Application, ApplicationEvent, Job, Profile, User
from app.guardrails.pii_scrubber import scrub_pii
from app.guardrails.rate_limiter import ApplicationRateLimiter, RateLimitExceeded
from app.models.schemas import ApplicationStatus

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Career Assistant", version="0.1.0")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    
    # Seed default verified jobs if none exist
    from app.db.database import get_session
    db = next(get_session())
    try:
        from app.db.models import Job
        existing_jobs = db.execute(select(Job)).scalars().all()
        if not existing_jobs:
            test_jobs = [
                Job(
                    external_id="job-1",
                    source="greenhouse",
                    title="Senior React Developer",
                    company="Vercel",
                    location="Remote (US)",
                    url="https://vercel.com/careers",
                    description="We are looking for a Senior React Developer to join our core framework team. You will work on optimizing Next.js rendering, building highly interactive developer consoles, and improving bundle performance. The ideal candidate has deep knowledge of React internals, server components, and modern frontend architectures.",
                    verified=True
                ),
                Job(
                    external_id="job-2",
                    source="lever",
                    title="Software Engineer - Frontend",
                    company="Stripe",
                    location="Remote / NYC",
                    url="https://stripe.com/careers",
                    description="Join the dashboard team at Stripe to build beautiful, highly accessible financial tools. You will implement robust frontend payment systems, manage complex state architectures, and ensure top-tier performance for millions of active merchants worldwide.",
                    verified=True
                ),
                Job(
                    external_id="job-3",
                    source="greenhouse",
                    title="Frontend Engineer",
                    company="Supabase",
                    location="Remote",
                    url="https://supabase.com/careers",
                    description="Looking for a Frontend Engineer to help us build the best open-source Firebase alternative. You will collaborate on the dashboard console, manage database visualizer interfaces, and build high-quality web experiences.",
                    verified=True
                )
            ]
            for job in test_jobs:
                db.add(job)
            db.commit()
    except Exception as e:
        print(f"Failed to seed jobs: {e}")



class CreateUser(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


@app.post("/users", status_code=201)
def create_user(body: CreateUser, db: Session = Depends(get_session)):
    email = body.email
    full_name = body.full_name
    first_name = body.first_name
    last_name = body.last_name
    
    if full_name and not (first_name or last_name):
        parts = full_name.split(" ")
        first_name = parts[0]
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
    elif (first_name or last_name) and not full_name:
        full_name = f"{first_name or ''} {last_name or ''}".strip()
        
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing:
        return {
            "user_id": existing.id,
            "id": existing.id,
            "email": existing.email,
            "full_name": existing.full_name,
            "first_name": existing.first_name,
            "last_name": existing.last_name
        }
        
    user = User(
        email=email, 
        full_name=full_name or "Test User", 
        first_name=first_name, 
        last_name=last_name
    )
    db.add(user)
    db.flush()
    return {
        "user_id": user.id,
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "first_name": user.first_name,
        "last_name": user.last_name
    }


@app.post("/users/{user_id}/cv")
async def upload_cv(user_id: str, file: UploadFile, db: Session = Depends(get_session)):
    """Store PII-scrubbed CV text; upload original binary to S3/disk; sync skills."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "user not found")
        
    raw_bytes = await file.read()
    raw = raw_bytes.decode(errors="replace")
    clean = scrub_pii(raw)
    
    # Save the original file to storage (S3 with local disk fallback)
    from app.services.s3_storage import upload_file_to_s3, save_file_locally
    cv_url_or_path = upload_file_to_s3(raw_bytes, file.filename, user.id)
    if not cv_url_or_path:
        cv_url_or_path = save_file_locally(raw_bytes, file.filename, user.id)
    
    from app.services.llm import extract_profile_from_cv
    profile_data = extract_profile_from_cv(clean, user.id, user.email, user.full_name)
    
    profile = db.execute(
        select(Profile).where(Profile.user_id == user_id)
    ).scalar_one_or_none()
    if profile:
        profile.cv_raw_text = clean
        profile.data = profile_data
        profile.cv_file_path = cv_url_or_path
        profile.version += 1
    else:
        profile = Profile(user_id=user_id, data=profile_data, cv_raw_text=clean, cv_file_path=cv_url_or_path)
        db.add(profile)
        
    db.flush()
    
    # Sync skills to user_skills table
    from app.services.profile_sync import sync_profile_skills_to_user_skills
    skills_list = profile_data.get("skills", [])
    sync_profile_skills_to_user_skills(db, user.id, skills_list)
    
    return {"profile_version": profile.version, "chars": len(clean), "profile_data": profile_data}


@app.get("/users/{user_id}/cv/download")
def download_cv(user_id: str, db: Session = Depends(get_session)):
    """Downloads/streams the original uploaded resume file."""
    profile = db.execute(
        select(Profile).where(Profile.user_id == user_id)
    ).scalar_one_or_none()
    
    if not profile or not profile.cv_file_path:
        raise HTTPException(404, "CV file not found for this user")
        
    path_or_url = profile.cv_file_path
    
    if path_or_url.startswith("http"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(path_or_url)
        
    import os
    if not os.path.exists(path_or_url):
        raise HTTPException(404, "CV file path does not exist on local disk")
        
    filename = os.path.basename(path_or_url)
    from fastapi.responses import FileResponse
    return FileResponse(path_or_url, filename=filename)


@app.get("/users/{user_id}/profile")
def get_user_profile(user_id: str, db: Session = Depends(get_session)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "user not found")
    profile = db.execute(
        select(Profile).where(Profile.user_id == user_id)
    ).scalar_one_or_none()
    if not profile:
        return {
            "user_id": user_id,
            "full_name": user.full_name,
            "email": user.email,
            "skills": [],
            "experience": [],
            "education": [],
            "locations": [],
            "target_roles": [],
            "profile_version": 0
        }
    return profile.data


@app.put("/users/{user_id}/profile")
def update_user_profile(user_id: str, body: dict, db: Session = Depends(get_session)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "user not found")
    profile = db.execute(
        select(Profile).where(Profile.user_id == user_id)
    ).scalar_one_or_none()
    if profile:
        profile.data = body
        profile.version += 1
    else:
        profile = Profile(user_id=user_id, data=body)
        db.add(profile)
        
    db.flush()
    
    # Sync skills to user_skills table if present in update
    if "skills" in body:
        from app.services.profile_sync import sync_profile_skills_to_user_skills
        sync_profile_skills_to_user_skills(db, user_id, body["skills"])
        
    return {"profile_version": profile.version}



@app.get("/jobs")
def list_jobs(
    q: str | None = None,
    verified_only: bool = True,
    limit: int = 50,
    db: Session = Depends(get_session),
):
    stmt = select(Job)
    if verified_only:  # verification gate: unverified jobs are never surfaced
        stmt = stmt.where(Job.verified.is_(True))
    if q:
        stmt = stmt.where(Job.title.ilike(f"%{q}%") | Job.description.ilike(f"%{q}%"))
    jobs = db.execute(stmt.order_by(Job.created_at.desc()).limit(limit)).scalars().all()
    return [
        {
            "id": j.id,
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "url": j.url,
            "source": j.source,
            "posted_at": j.posted_at,
        }
        for j in jobs
    ]


@app.post("/users/{user_id}/jobs/{job_id}/select", status_code=201)
def select_job(user_id: str, job_id: str, db: Session = Depends(get_session)):
    """User picks a job -> draft application created; document generation is queued."""
    if not db.get(User, user_id):
        raise HTTPException(404, "user not found")
    job = db.get(Job, job_id)
    if not job or not job.verified:
        raise HTTPException(404, "verified job not found")
    application = Application(user_id=user_id, job_id=job_id, status=ApplicationStatus.DRAFT.value)
    db.add(application)
    db.flush()
    db.add(ApplicationEvent(application_id=application.id, event="created"))
    from app.pipeline import queue

    queue.publish(
        queue.get_redis(),
        queue.DOCS_REQUESTED,
        {"application_id": application.id, "user_id": user_id, "job_id": job_id},
    )
    return {"application_id": application.id, "status": application.status}


class ApproveBody(BaseModel):
    contact_email: EmailStr | None = None


@app.post("/applications/{application_id}/approve")
def approve_application(
    application_id: str,
    body: ApproveBody | None = None,
    db: Session = Depends(get_session),
):
    """Human-in-the-loop gate: nothing is submitted without this call."""
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "application not found")
    if application.status != ApplicationStatus.AWAITING_USER_APPROVAL.value:
        raise HTTPException(409, f"cannot approve from status '{application.status}'")
    job = db.get(Job, application.job_id)
    try:
        ApplicationRateLimiter().check_and_increment(application.user_id, job.source)
    except RateLimitExceeded as exc:
        raise HTTPException(429, str(exc)) from exc
    application.status = ApplicationStatus.APPROVED.value
    db.add(ApplicationEvent(application_id=application.id, event="approved_by_user"))
    from app.pipeline import queue

    queue.publish(
        queue.get_redis(),
        queue.APPROVED,
        {
            "application_id": application.id,
            "contact_email": body.contact_email if body else None,
        },
    )
    return {"application_id": application.id, "status": application.status}


@app.post("/applications/{application_id}/reject")
def reject_application(application_id: str, db: Session = Depends(get_session)):
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "application not found")
    application.status = ApplicationStatus.REJECTED_BY_USER.value
    db.add(ApplicationEvent(application_id=application.id, event="rejected_by_user"))
    return {"application_id": application.id, "status": application.status}


@app.get("/applications/{application_id}")
def application_status(application_id: str, db: Session = Depends(get_session)):
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "application not found")
    events = db.execute(
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == application_id)
        .order_by(ApplicationEvent.created_at)
    ).scalars().all()
    return {
        "application_id": application.id,
        "status": application.status,
        "submitted_at": application.submitted_at,
        "confirmation_ref": application.confirmation_ref,
        "events": [{"event": e.event, "at": e.created_at} for e in events],
    }


@app.get("/users/{user_id}/jobs/{job_id}/match")
def job_match(user_id: str, job_id: str, db: Session = Depends(get_session)):
    """Compatibility score, cached by (user, job, profile_version)."""
    from app.services.matching import get_or_compute_match

    try:
        row = get_or_compute_match(db, user_id, job_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"score": row.score, "profile_version": row.profile_version, **row.detail}


@app.get("/users/{user_id}/roadmap")
def learning_roadmap(
    user_id: str, target_role: str | None = None, db: Session = Depends(get_session)
):
    """Skill-gap roadmap aggregated from the user's cached match scores."""
    from app.services.skillgap import build_roadmap

    try:
        return build_roadmap(db, user_id, target_role).model_dump()
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


class StartInterview(BaseModel):
    role: str


@app.post("/users/{user_id}/interview/start", status_code=201)
def start_interview(user_id: str, body: StartInterview, db: Session = Depends(get_session)):
    if not db.get(User, user_id):
        raise HTTPException(404, "user not found")
    from app.services.interview import start_session

    session, first_question = start_session(db, user_id, body.role)
    return {"session_id": session.id, "question": first_question}


class UnifiedInterviewAnswer(BaseModel):
    answer: str
    question_index: Optional[int] = None


@app.post("/interview/{session_id}/answer")
def answer_interview(session_id: str, body: UnifiedInterviewAnswer, db: Session = Depends(get_session)):
    """Score the current answer and return feedback plus the next question (handles both backends)."""
    from app.db.models import InterviewSession as TalhaInterviewSession, MABDInterviewSession
    
    # 1. Check if it's a Talha Interview session
    talha_session = db.get(TalhaInterviewSession, session_id)
    if talha_session:
        from app.services.interview import submit_answer
        try:
            return submit_answer(db, talha_session, body.answer)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    # 2. Check if it's a MABD Interview session
    mabd_session = db.get(MABDInterviewSession, session_id)
    if mabd_session:
        raise HTTPException(
            status_code=400,
            detail="Django/MABD interview sessions are handled by the Django server running on port 8002."
        )

    raise HTTPException(404, "session not found")


@app.get("/interview/{session_id}")
def interview_transcript(session_id: str, db: Session = Depends(get_session)):
    from app.db.models import InterviewSession as TalhaInterviewSession, MABDInterviewSession

    # 1. Check if it's a Talha Interview session
    talha_session = db.get(TalhaInterviewSession, session_id)
    if talha_session:
        from app.db.models import InterviewTurn
        turns = db.execute(
            select(InterviewTurn)
            .where(InterviewTurn.session_id == session_id)
            .order_by(InterviewTurn.created_at)
        ).scalars().all()
        scores = [t.score for t in turns if t.score is not None]
        return {
            "session_id": talha_session.id,
            "role": talha_session.role,
            "completed": talha_session.completed,
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "turns": [
                {"question": t.question, "answer": t.answer, "score": t.score, "feedback": t.feedback}
                for t in turns
            ],
            "type": "talha"
        }

    # 2. Check if it's a MABD Interview session
    mabd_session = db.get(MABDInterviewSession, session_id)
    if mabd_session:
        return {
            "id": mabd_session.id,
            "user_id": mabd_session.user_id,
            "job_id": mabd_session.job_id,
            "question_set": mabd_session.question_set,
            "responses": mabd_session.responses,
            "feedback": mabd_session.feedback,
            "score": mabd_session.score,
            "status": mabd_session.status,
            "created_at": mabd_session.created_at,
            "type": "mabd"
        }

    raise HTTPException(404, "session not found")


@app.get("/healthz")
def healthz():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}
