"""Structured outputs for every pipeline stage.

Every agent receives/returns one of these models (passed as ``output_type``
to the OpenAI Agents SDK) so inter-agent communication never relies on
free-text parsing.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class JobSource(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    AGGREGATOR = "aggregator"


class JobListing(BaseModel):
    external_id: str
    source: JobSource
    title: str
    company: str
    location: str | None = None
    url: str
    description: str = ""
    posted_at: datetime | None = None


class VerifiedJob(BaseModel):
    """Output of the Job Verification Agent."""

    job: JobListing
    verified_status: bool
    duplicate: bool = False
    expired: bool = False
    suspicious: bool = False
    reasons: list[str] = Field(default_factory=list)


class ExperienceEntry(BaseModel):
    title: str
    company: str
    start: str | None = None
    end: str | None = None
    highlights: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    degree: str
    institution: str
    year: str | None = None


class UserProfile(BaseModel):
    """Canonical parsed-CV profile. Source of truth for the factual checker."""

    user_id: str
    full_name: str
    email: EmailStr
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    profile_version: int = 1


class MatchScore(BaseModel):
    """Output of the Job Matching Agent."""

    job_external_id: str
    user_id: str
    score: float = Field(ge=0, le=100)
    skill_overlap: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    rationale: str = ""


class ResumeDiff(BaseModel):
    """Output of the Resume Optimization Agent.

    ``source_claims`` lists every factual claim used, each of which must be
    entailed by the UserProfile (enforced by the factual-accuracy guardrail).
    """

    job_external_id: str
    resume_markdown: str
    highlighted_skills: list[str] = Field(default_factory=list)
    source_claims: list[str] = Field(default_factory=list)


class CoverLetter(BaseModel):
    job_external_id: str
    body_markdown: str
    source_claims: list[str] = Field(default_factory=list)


class ApplicationStatus(str, Enum):
    DRAFT = "draft"
    AWAITING_USER_APPROVAL = "awaiting_user_approval"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    REJECTED_BY_USER = "rejected_by_user"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED_BY_COMPANY = "rejected_by_company"


class ApplicationRecord(BaseModel):
    application_id: str
    user_id: str
    job_external_id: str
    status: ApplicationStatus = ApplicationStatus.DRAFT
    resume_markdown: str | None = None
    cover_letter_markdown: str | None = None
    submitted_at: datetime | None = None
    confirmation_ref: str | None = None


class InterviewFeedback(BaseModel):
    question: str
    answer_summary: str
    score: float = Field(ge=0, le=10)
    feedback: str


class LearningRoadmapItem(BaseModel):
    skill: str
    priority: int = Field(ge=1, le=5)
    resources: list[str] = Field(default_factory=list)
    estimated_weeks: int = 1


class LearningRoadmap(BaseModel):
    user_id: str
    target_role: str
    items: list[LearningRoadmapItem] = Field(default_factory=list)
