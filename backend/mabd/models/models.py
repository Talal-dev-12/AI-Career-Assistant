from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlmodel import SQLModel

# Import unified table models from the central database package
from app.db.models import (
    User,
    UserSkill,
    Job,
    SkillGapAnalysis,
    MABDInterviewSession as InterviewSession
)

# ================= API Schemas (Pydantic / SQLModel) =================

class UserCreate(SQLModel):
    email: str
    first_name: str
    last_name: str

class SkillCreate(SQLModel):
    skill_name: str
    proficiency_level: str
    years_experience: float

class JobCreate(SQLModel):
    title: str
    company_name: str
    description: str
    required_skills: List[str]
    location: str
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None

class SkillGapRequest(SQLModel):
    user_id: str  # changed to str for UUID compatibility
    job_id: str   # changed to str for UUID compatibility

class InterviewStartRequest(SQLModel):
    user_id: str  # changed to str for UUID compatibility
    job_id: str   # changed to str for UUID compatibility

class AnswerSubmitRequest(SQLModel):
    question_index: int
    answer: str

# --- Read/Response Models (Pydantic v2 from_attributes = True) ---

class UserSkillRead(SQLModel):
    id: str
    user_id: str
    skill_name: str
    proficiency_level: str
    years_experience: float

    model_config = {"from_attributes": True}

class JobRead(SQLModel):
    id: str
    title: str
    company: str
    company_name: Optional[str] = None
    description: str
    required_skills: Optional[List[str]] = None
    location: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    verified: bool

    model_config = {"from_attributes": True}

class SkillGapAnalysisRead(SQLModel):
    id: str
    user_id: str
    job_id: str
    missing_skills: List[Any]
    proficiency_gap: List[Any]
    learning_roadmap: List[Any]
    salary_projection: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class InterviewSessionRead(SQLModel):
    id: str
    user_id: str
    job_id: str
    question_set: List[str]
    responses: List[str]
    feedback: Dict[str, Any]
    score: Optional[int] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
