from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profile: Mapped[Profile | None] = relationship(back_populates="user", uselist=False)
    
    # MABD Relationships
    skills: Mapped[list[UserSkill]] = relationship(back_populates="user", cascade="all, delete-orphan")
    analyses: Mapped[list[SkillGapAnalysis]] = relationship(back_populates="user", cascade="all, delete-orphan")
    mabd_interviews: Mapped[list[MABDInterviewSession]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    data: Mapped[dict] = mapped_column(JSON)  # serialized UserProfile
    version: Mapped[int] = mapped_column(Integer, default=1)
    cv_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    cv_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped[User] = relationship(back_populates="profile")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    external_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(512))
    company: Mapped[str] = mapped_column(String(255), index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    required_skills: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # MABD Relationships
    analyses: Mapped[list[SkillGapAnalysis]] = relationship(back_populates="job", cascade="all, delete-orphan")
    mabd_interviews: Mapped[list[MABDInterviewSession]] = relationship(back_populates="job", cascade="all, delete-orphan")


class MatchScoreRow(Base):
    __tablename__ = "match_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    profile_version: Mapped[int] = mapped_column(Integer)  # cache key part
    score: Mapped[float] = mapped_column(Float)
    detail: Mapped[dict] = mapped_column(JSON)  # serialized MatchScore
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    resume_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmation_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    event: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(255))
    question_index: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InterviewTurn(Base):
    __tablename__ = "interview_turns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ================= MABD Models (SQLAlchemy Declarative Style) =================

class UserSkill(Base):
    __tablename__ = "user_skills"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    skill_name: Mapped[str] = mapped_column(String(255), index=True)
    proficiency_level: Mapped[str] = mapped_column(String(50))  # Beginner, Intermediate, Expert
    years_experience: Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    user: Mapped[User] = relationship(back_populates="skills")


class SkillGapAnalysis(Base):
    __tablename__ = "skill_gap_analyses"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    missing_skills: Mapped[list] = mapped_column(JSON, default=list)
    proficiency_gap: Mapped[list] = mapped_column(JSON, default=list)
    learning_roadmap: Mapped[list] = mapped_column(JSON, default=list)
    salary_projection: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped[User] = relationship(back_populates="analyses")
    job: Mapped[Job] = relationship(back_populates="analyses")


class MABDInterviewSession(Base):
    __tablename__ = "mabd_interview_sessions"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    question_set: Mapped[list] = mapped_column(JSON, default=list)
    responses: Mapped[list] = mapped_column(JSON, default=list)
    feedback: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="started")  # started, completed, evaluated
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped[User] = relationship(back_populates="mabd_interviews")
    job: Mapped[Job] = relationship(back_populates="mabd_interviews")
