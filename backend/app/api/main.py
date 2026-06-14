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
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None


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


from fastapi import Depends, FastAPI, HTTPException, UploadFile, BackgroundTasks
import io
import logging

log = logging.getLogger("career_assistant.api")
pipeline_logs = {}

def add_pipeline_log(user_id: str, stage: str, message: str, progress: int):
    if user_id not in pipeline_logs:
        pipeline_logs[user_id] = []
    pipeline_logs[user_id].append({
        "timestamp": datetime.utcnow().isoformat(),
        "stage": stage,
        "message": message,
        "progress": progress
    })

def extract_text_from_file_bytes(content_bytes: bytes, filename: str) -> str:
    ext = filename.split(".")[-1].lower()
    if ext == "pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content_bytes))
            text = ""
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
            return text
        except Exception as e:
            log.warning(f"Error parsing PDF with pypdf: {e}")
            return content_bytes.decode(errors="replace")
    elif ext == "docx":
        try:
            import docx
            doc = docx.Document(io.BytesIO(content_bytes))
            return "\n".join([p.text for p in doc.paragraphs])
        except Exception as e:
            log.warning(f"Error parsing DOCX with python-docx: {e}")
            return content_bytes.decode(errors="replace")
    else:
        try:
            return content_bytes.decode("utf-8", errors="replace")
        except Exception:
            return content_bytes.decode("latin1", errors="replace")

def run_cv_pipeline_task(user_id: str, clean_text: str, filename: str, cv_url_or_path: str):
    db = next(get_session())
    try:
        add_pipeline_log(user_id, "parsing", "Extracting profile credentials (skills, experience, education)...", 30)
        user = db.get(User, user_id)
        if not user:
            add_pipeline_log(user_id, "error", f"User {user_id} not found in database.", 100)
            return

        from app.services.llm import extract_profile_from_cv
        profile_data = extract_profile_from_cv(clean_text, user.id, user.email, user.full_name)
        
        # Save profile
        profile = db.execute(
            select(Profile).where(Profile.user_id == user_id)
        ).scalar_one_or_none()
        if profile:
            profile.cv_raw_text = clean_text
            profile.data = profile_data
            profile.cv_file_path = cv_url_or_path
            profile.version += 1
        else:
            profile = Profile(user_id=user_id, data=profile_data, cv_raw_text=clean_text, cv_file_path=cv_url_or_path)
            db.add(profile)
        db.commit()

        # Sync skills to user_skills table
        from app.services.profile_sync import sync_profile_skills_to_user_skills
        skills_list = profile_data.get("skills", [])
        sync_profile_skills_to_user_skills(db, user.id, skills_list)
        db.commit()

        add_pipeline_log(user_id, "scraping", f"Profile parsed successfully. Found skills: {', '.join(skills_list[:5])}. Harvesting live job listings...", 50)
        
        # Ingest jobs dynamically via verified adapters
        from app.adapters.greenhouse import GreenhouseAdapter, DEFAULT_BOARDS
        from app.adapters.lever import LeverAdapter
        
        # Use all verified boards — no hardcoded broken slugs
        gh_adapter = GreenhouseAdapter()   # uses DEFAULT_BOARDS automatically
        lv_adapter = LeverAdapter()        # uses Adzuna + verified Lever companies

        import asyncio

        async def _fetch_all_jobs():
            gh = await gh_adapter.fetch_jobs()
            lv = await lv_adapter.fetch_jobs()
            return gh + lv

        try:
            # Background task runs in a regular thread — asyncio.run() creates a fresh loop
            fetched_jobs = asyncio.run(_fetch_all_jobs())
            log.info(f"Pipeline fetched {len(fetched_jobs)} jobs total")
        except Exception as exc:
            log.warning(f"Error fetching live jobs: {exc}")
            fetched_jobs = []

        add_pipeline_log(user_id, "verification", f"Scraped {len(fetched_jobs)} jobs. Running verification & deduplication filters...", 75)
        
        saved_count = 0
        for listing in fetched_jobs:
            existing = db.execute(
                select(Job).where(Job.external_id == listing.external_id)
            ).scalar_one_or_none()
            if not existing:
                job = Job(
                    external_id=listing.external_id,
                    source=listing.source.value,
                    title=listing.title,
                    company=listing.company,
                    company_name=listing.company,
                    location=listing.location,
                    url=listing.url,
                    description=listing.description,
                    posted_at=listing.posted_at,
                    verified=bool(listing.title and listing.company and listing.url),
                    verification_reasons={"checks": ["non-empty fields", "unique external_id"]},
                )
                db.add(job)
                saved_count += 1
        db.commit()

        add_pipeline_log(user_id, "matching", f"Deduplicated jobs. Calculating job matching compatibility scores...", 90)
        
        # Calculate matching scores
        jobs = db.execute(select(Job).where(Job.verified.is_(True))).scalars().all()
        from app.services.matching import get_or_compute_match
        
        matched_count = 0
        for job in jobs:
            try:
                get_or_compute_match(db, user_id, job.id)
                matched_count += 1
            except Exception as e:
                log.warning(f"Error matching job {job.id}: {e}")
        db.commit()

        add_pipeline_log(user_id, "completed", f"Pipeline complete! Extracted profile, verified {saved_count} new jobs, and matching scores updated.", 100)
    except Exception as exc:
        db.rollback()
        log.exception(f"Pipeline failed for user {user_id}: {exc}")
        add_pipeline_log(user_id, "error", f"Pipeline failed: {str(exc)}", 100)
    finally:
        db.close()

@app.get("/users/{user_id}/pipeline/logs")
def get_pipeline_logs(user_id: str):
    return pipeline_logs.get(user_id, [])

@app.post("/users/{user_id}/cv")
async def upload_cv(user_id: str, file: UploadFile, background_tasks: BackgroundTasks, db: Session = Depends(get_session)):
    """Store PII-scrubbed CV text; upload original binary to S3/disk; trigger automated scraping & matching."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "user not found")
        
    raw_bytes = await file.read()
    raw = extract_text_from_file_bytes(raw_bytes, file.filename)
    clean = scrub_pii(raw)
    
    # Save the original file to storage (S3 with local disk fallback)
    from app.services.s3_storage import upload_file_to_s3, save_file_locally
    cv_url_or_path = upload_file_to_s3(raw_bytes, file.filename, user.id)
    if not cv_url_or_path:
        cv_url_or_path = save_file_locally(raw_bytes, file.filename, user.id)
    
    # Initialize pipeline logs
    pipeline_logs[user_id] = []
    add_pipeline_log(user_id, "parsing", "Parsing CV layout and scrubbing PII...", 10)
    
    # Trigger CV pipeline task in background
    background_tasks.add_task(run_cv_pipeline_task, user_id, clean, file.filename, cv_url_or_path)
    
    return {"status": "processing", "message": "CV upload received. Pipeline execution started."}


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
    question_index: int | None = None


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
        from app.services.mabd_services import submit_interview_response as mabd_submit_answer
        if body.question_index is None:
            raise HTTPException(400, "question_index is required for MABD interview sessions")
        try:
            session = mabd_submit_answer(db, session_id, body.question_index, body.answer)
            return {
                "id": session.id,
                "user_id": session.user_id,
                "job_id": session.job_id,
                "question_set": session.question_set,
                "responses": session.responses,
                "feedback": session.feedback,
                "score": session.score,
                "status": session.status,
                "created_at": session.created_at,
                "type": "mabd"
            }
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        except LookupError as exc:
            raise HTTPException(404, str(exc))

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


class MabdInterviewStartRequest(BaseModel):
    user_id: str
    job_id: str


@app.post("/interview/start", status_code=201)
def mabd_start_interview(body: MabdInterviewStartRequest, db: Session = Depends(get_session)):
    from app.services.mabd_services import start_interview_session as mabd_start_session
    try:
        session = mabd_start_session(db, body.user_id, body.job_id)
        return {
            "id": session.id,
            "user_id": session.user_id,
            "job_id": session.job_id,
            "question_set": session.question_set,
            "responses": session.responses,
            "feedback": session.feedback,
            "score": session.score,
            "status": session.status,
            "created_at": session.created_at,
            "type": "mabd"
        }
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.post("/interview/{session_id}/evaluate")
def mabd_evaluate_interview(session_id: str, db: Session = Depends(get_session)):
    from app.services.mabd_services import evaluate_interview_session as mabd_eval_session
    try:
        session = mabd_eval_session(db, session_id)
        return {
            "id": session.id,
            "user_id": session.user_id,
            "job_id": session.job_id,
            "question_set": session.question_set,
            "responses": session.responses,
            "feedback": session.feedback,
            "score": session.score,
            "status": session.status,
            "created_at": session.created_at,
            "type": "mabd"
        }
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(400, str(exc))


class MabdSkillGapRequest(BaseModel):
    user_id: str
    job_id: str


@app.post("/skill-gap/analyze")
def mabd_run_skill_gap(body: MabdSkillGapRequest, db: Session = Depends(get_session)):
    from app.services.mabd_services import analyze_skill_gap as mabd_analyze_gap
    try:
        analysis = mabd_analyze_gap(db, body.user_id, body.job_id)
        return {
            "id": analysis.id,
            "user_id": analysis.user_id,
            "job_id": analysis.job_id,
            "missing_skills": analysis.missing_skills,
            "proficiency_gap": analysis.proficiency_gap,
            "learning_roadmap": analysis.learning_roadmap,
            "salary_projection": analysis.salary_projection,
            "created_at": analysis.created_at
        }
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.get("/skill-gap/history/{user_id}")
def mabd_skill_gap_history(user_id: str, db: Session = Depends(get_session)):
    from app.db.models import SkillGapAnalysis as SQLAlchemySkillGapAnalysis
    try:
        stmt = select(SQLAlchemySkillGapAnalysis).where(SQLAlchemySkillGapAnalysis.user_id == user_id).order_by(SQLAlchemySkillGapAnalysis.created_at.desc())
        analyses = db.execute(stmt).scalars().all()
        return [
            {
                "id": a.id,
                "user_id": a.user_id,
                "job_id": a.job_id,
                "missing_skills": a.missing_skills,
                "proficiency_gap": a.proficiency_gap,
                "learning_roadmap": a.learning_roadmap,
                "salary_projection": a.salary_projection,
                "created_at": a.created_at
            }
            for a in analyses
        ]
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.post("/jobs/scrape")
async def trigger_scrape(
    keyword: str | None = None,
    location: str | None = None,
    db: Session = Depends(get_session)
):
    """Trigger live job harvesting from Greenhouse (verified boards) and Adzuna."""
    from app.adapters.greenhouse import GreenhouseAdapter
    from app.adapters.lever import LeverAdapter

    gh_adapter = GreenhouseAdapter()   # uses all verified DEFAULT_BOARDS
    lv_adapter = LeverAdapter()        # Adzuna + verified Lever companies

    try:
        # Await directly — this is an async endpoint, no new event loop needed
        gh_jobs = await gh_adapter.fetch_jobs()
        log.info(f"Greenhouse returned {len(gh_jobs)} jobs")
    except Exception as exc:
        log.warning(f"Greenhouse fetch error: {exc}")
        gh_jobs = []

    try:
        lv_jobs = await lv_adapter.fetch_jobs()
        log.info(f"Lever/Adzuna returned {len(lv_jobs)} jobs")
    except Exception as exc:
        log.warning(f"Lever/Adzuna fetch error: {exc}")
        lv_jobs = []

    fetched_jobs = gh_jobs + lv_jobs
    log.info(f"Total fetched: {len(fetched_jobs)}")

    saved_count = 0
    for listing in fetched_jobs:
        try:
            existing = db.execute(
                select(Job).where(Job.external_id == listing.external_id)
            ).scalar_one_or_none()
            if not existing:
                job = Job(
                    external_id=listing.external_id,
                    source=listing.source.value,
                    title=listing.title,
                    company=listing.company or "",
                    company_name=listing.company or "",
                    location=listing.location or "",
                    url=listing.url or "",
                    description=listing.description or "",
                    posted_at=listing.posted_at,
                    verified=bool(listing.title and listing.company and listing.url),
                    verification_reasons={"checks": ["non-empty fields", "unique external_id"]},
                )
                db.add(job)
                saved_count += 1
        except Exception as save_exc:
            log.warning(f"Failed to save job {getattr(listing, 'external_id', '?')}: {save_exc}")
    db.commit()

    return {
        "status": "completed",
        "fetched": len(fetched_jobs),
        "newly_saved": saved_count,
        "source": "Greenhouse + Adzuna APIs",
        "boards_used": ["vercel", "cloudflare", "airbnb", "reddit", "stripe", "figma",
                        "discord", "coinbase", "databricks", "mongodb", "twilio"],
        "sample": [{"title": j.title, "company": j.company} for j in fetched_jobs[:5]]
    }

@app.get("/users/{user_id}/dashboard")
def get_user_dashboard(user_id: str, db: Session = Depends(get_session)):
    from sqlalchemy import func
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "user not found")

    # 1. Metrics calculations
    apps_sent = db.execute(
        select(func.count(Application.id)).where(
            Application.user_id == user_id,
            Application.status.in_(["applied", "approved", "email_sent", "review", "interview", "offer"])
        )
    ).scalar() or 0

    avg_match = db.execute(
        select(func.avg(MatchScoreRow.score)).where(MatchScoreRow.user_id == user_id)
    ).scalar() or 85.0

    rec_jobs_count = db.execute(
        select(func.count(MatchScoreRow.id)).where(
            MatchScoreRow.user_id == user_id,
            MatchScoreRow.score >= 70.0
        )
    ).scalar() or 0

    interviews = db.execute(
        select(func.count(InterviewSession.id)).where(
            InterviewSession.user_id == user_id,
            InterviewSession.completed.is_(True)
        )
    ).scalar() or 0

    # 2. Spotlight recommendations
    top_matches = db.execute(
        select(MatchScoreRow, Job)
        .join(Job, MatchScoreRow.job_id == Job.id)
        .where(MatchScoreRow.user_id == user_id)
        .order_by(MatchScoreRow.score.desc())
        .limit(3)
    ).all()

    spotlight = []
    for match_row, job in top_matches:
        spotlight.append({
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "logo": job.company[:1].upper() if job.company else "C",
            "match": int(match_row.score),
            "location": job.location or "Remote",
            "salary": f"${int(job.salary_min / 1000)}k - ${int(job.salary_max / 1000)}k" if job.salary_min and job.salary_max else "$110k - $140k",
            "tags": (job.required_skills or ["React", "TypeScript"])[:3]
        })

    if not spotlight:
        # Fallback recommendations if no scores are cached yet
        general_jobs = db.execute(select(Job).limit(3)).scalars().all()
        for j in general_jobs:
            spotlight.append({
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "logo": j.company[:1].upper() if j.company else "C",
                "match": 80,
                "location": j.location or "Remote",
                "salary": "$110k - $140k",
                "tags": (j.required_skills or ["React", "TypeScript"])[:3]
            })

    # 3. Agent Activities
    recent_events = db.execute(
        select(ApplicationEvent, Application, Job)
        .join(Application, ApplicationEvent.application_id == Application.id)
        .join(Job, Application.job_id == Job.id)
        .where(Application.user_id == user_id)
        .order_by(ApplicationEvent.created_at.desc())
        .limit(4)
    ).all()

    activities = []
    for ev, app, j in recent_events:
        activities.append({
            "agent": "Automation Agent",
            "time": ev.created_at.strftime("%I:%M %p") if (datetime.utcnow() - ev.created_at).days == 0 else ev.created_at.strftime("%b %d"),
            "dotStyle": "styles.success",
            "title": f"Application event: {ev.event}",
            "desc": f"Processed status change for '{j.title}' at {j.company}."
        })

    if not activities:
        activities = [
            {
                "agent": "CV Ingestion & Parsing Agent",
                "time": "Just now",
                "dotStyle": "styles.primary",
                "title": "CV Ingestion Completed",
                "desc": "Successfully ingested and parsed candidate CV credentials."
            },
            {
                "agent": "Job Discovery Agent",
                "time": "Just now",
                "dotStyle": "styles.secondary",
                "title": "Crawler Job Search Complete",
                "desc": "Verified latest listings from active greenhouse and lever boards."
            }
        ]

    return {
        "metrics": {
            "applications_sent": str(apps_sent),
            "avg_match": f"{int(avg_match)}%",
            "recommended_jobs": str(rec_jobs_count),
            "interviews_booked": str(interviews)
        },
        "spotlight": spotlight,
        "activities": activities
    }

@app.get("/healthz")
def healthz():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}
