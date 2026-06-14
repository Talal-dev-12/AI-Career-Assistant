from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from mabd.database.db import get_session
from mabd.models.models import (
    User, UserSkill, Job, SkillGapAnalysis, 
    UserCreate, SkillCreate, JobCreate, SkillGapRequest,
    UserSkillRead, JobRead, SkillGapAnalysisRead
)
from mabd.services.skill_service import analyze_skill_gap

router = APIRouter(tags=["Skill Gap Analysis"])

# --- User & Skills Management Endpoints ---
# Commented out duplicate create_user endpoint; handled by unified POST /users in app.api.main
# @router.post("/users", response_model=User, status_code=201)
# def create_user(user_data: UserCreate, session: Session = Depends(get_session)):
#     # Check if email exists
#     existing = session.exec(select(User).where(User.email == user_data.email)).first()
#     if existing:
#         raise HTTPException(status_code=400, detail="Email already registered")
#     
#     db_user = User(
#         email=user_data.email,
#         first_name=user_data.first_name,
#         last_name=user_data.last_name,
#         full_name=f"{user_data.first_name} {user_data.last_name}"
#     )
#     session.add(db_user)
#     session.commit()
#     session.refresh(db_user)
#     return db_user

@router.post("/users/{user_id}/skills", response_model=UserSkillRead, status_code=201)
def add_user_skill(user_id: str, skill_data: SkillCreate, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    db_skill = UserSkill(
        user_id=user_id,
        skill_name=skill_data.skill_name,
        proficiency_level=skill_data.proficiency_level,
        years_experience=skill_data.years_experience
    )
    session.add(db_skill)
    session.commit()
    session.refresh(db_skill)
    
    # Sync skills back to user profile data
    try:
        from app.services.profile_sync import sync_user_skills_to_profile
        sync_user_skills_to_profile(session, user_id)
        session.commit()
    except Exception as e:
        # Log or print error, don't fail the primary transaction
        print(f"Failed to sync user skills to profile: {e}")
        
    return db_skill

@router.get("/users/{user_id}/skills", response_model=List[UserSkillRead])
def get_user_skills(user_id: str, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.skills

# --- Jobs Management Endpoints ---

@router.post("/jobs", response_model=JobRead, status_code=201)
def create_job(job_data: JobCreate, session: Session = Depends(get_session)):
    db_job = Job(
        title=job_data.title,
        company=job_data.company_name,
        company_name=job_data.company_name,
        description=job_data.description,
        required_skills=job_data.required_skills,
        location=job_data.location,
        salary_min=job_data.salary_min,
        salary_max=job_data.salary_max,
        verified=True,
        external_id=f"mabd-{uuid_str()[:8]}"
    )
    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    return db_job

def uuid_str() -> str:
    import uuid
    return str(uuid.uuid4())

# Commented out duplicate list_jobs endpoint; handled by unified GET /jobs in app.api.main
# @router.get("/jobs", response_model=List[Job])
# def list_jobs(session: Session = Depends(get_session)):
#     return session.exec(select(Job)).all()

# --- Skill Gap Analysis Endpoints ---

@router.post("/skill-gap/analyze", response_model=SkillGapAnalysisRead, status_code=200)
def run_analysis(request: SkillGapRequest, session: Session = Depends(get_session)):
    return analyze_skill_gap(
        session=session,
        user_id=request.user_id,
        job_id=request.job_id
    )

@router.get("/skill-gap/history/{user_id}", response_model=List[SkillGapAnalysisRead])
def get_analysis_history(user_id: str, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.analyses

@router.get("/skill-gap/{analysis_id}", response_model=SkillGapAnalysisRead)
def get_analysis_by_id(analysis_id: str, session: Session = Depends(get_session)):
    analysis = session.get(SkillGapAnalysis, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis report not found")
    return analysis