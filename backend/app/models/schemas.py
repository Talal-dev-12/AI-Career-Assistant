"""Structured outputs for every pipeline stage and inter-service contracts.

Every agent receives/returns one of these models (passed as ``output_type``
to the OpenAI Agents SDK) so inter-agent communication never relies on
free-text parsing.

Pydantic v2 schemas — request validation, response serialization, and inter-service contracts.
"""
from __future__ import annotations

import uuid
from datetime import datetime, UTC
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator, model_validator


# ── Job / Profile / Matching Schemas ──────────────────────────────────────────

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


# ── Application Status and Transitions ────────────────────────────────────────

class ApplicationStatus(str, Enum):
    # From HEAD
    DRAFT = "draft"
    AWAITING_USER_APPROVAL = "awaiting_user_approval"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    REJECTED_BY_USER = "rejected_by_user"
    OFFER = "offer"
    REJECTED_BY_COMPANY = "rejected_by_company"
    
    # From hammad
    QUEUED             = "queued"
    PROCESSING         = "processing"
    APPLIED            = "applied"
    PENDING_APPROVAL   = "pending_approval"
    CAPTCHA_REQUIRED   = "captcha_required"
    FAILED             = "failed"
    DUPLICATE          = "duplicate"
    LIMIT_EXCEEDED     = "limit_exceeded"
    EXPIRED            = "expired"
    ASSET_ERROR        = "asset_error"
    REJECTED           = "rejected"
    INTERVIEW          = "interview"
    ACCEPTED           = "accepted"
    # Email-specific statuses
    EMAIL_QUEUED       = "email_queued"
    EMAIL_SENDING      = "email_sending"
    EMAIL_SENT         = "email_sent"
    EMAIL_FAILED       = "email_failed"


class ApplicationMethod(str, Enum):
    EMAIL              = "email"
    WEB_FORM           = "web_form"
    LINKEDIN_EASY_APPLY = "linkedin_easy_apply"
    ATS_PORTAL         = "ats_portal"
    MANUAL             = "manual"


class ApplicationPriority(str, Enum):
    LOW    = "low"
    NORMAL = "normal"
    HIGH   = "high"


VALID_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.QUEUED: {
        ApplicationStatus.PROCESSING,
        ApplicationStatus.PENDING_APPROVAL,
        ApplicationStatus.LIMIT_EXCEEDED,
        ApplicationStatus.DUPLICATE,
        ApplicationStatus.EXPIRED,
        ApplicationStatus.EMAIL_QUEUED,
        ApplicationStatus.EMAIL_SENDING,
        ApplicationStatus.FAILED,
    },
    ApplicationStatus.PENDING_APPROVAL: {
        ApplicationStatus.QUEUED,
        ApplicationStatus.EMAIL_QUEUED,
        ApplicationStatus.FAILED,
    },
    ApplicationStatus.PROCESSING: {
        ApplicationStatus.APPLIED,
        ApplicationStatus.FAILED,
        ApplicationStatus.CAPTCHA_REQUIRED,
        ApplicationStatus.ASSET_ERROR,
    },
    ApplicationStatus.APPLIED: {
        ApplicationStatus.REJECTED,
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.ACCEPTED,
    },
    ApplicationStatus.CAPTCHA_REQUIRED: {
        ApplicationStatus.PROCESSING,
        ApplicationStatus.FAILED,
    },
    # Email-specific transitions
    ApplicationStatus.EMAIL_QUEUED: {
        ApplicationStatus.EMAIL_SENDING,
        ApplicationStatus.EMAIL_FAILED,
        ApplicationStatus.FAILED,
    },
    ApplicationStatus.EMAIL_SENDING: {
        ApplicationStatus.EMAIL_SENT,
        ApplicationStatus.EMAIL_FAILED,
        ApplicationStatus.FAILED,
    },
    ApplicationStatus.EMAIL_FAILED: {
        ApplicationStatus.EMAIL_SENDING,
        ApplicationStatus.FAILED,
    },
    ApplicationStatus.EMAIL_SENT: {
        ApplicationStatus.REJECTED,
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.ACCEPTED,
    },
    # Terminal states — no transitions allowed out
    ApplicationStatus.FAILED: set(),
    ApplicationStatus.DUPLICATE: set(),
    ApplicationStatus.LIMIT_EXCEEDED: set(),
    ApplicationStatus.EXPIRED: set(),
    ApplicationStatus.REJECTED: set(),
    ApplicationStatus.ACCEPTED: set(),
    ApplicationStatus.INTERVIEW: {ApplicationStatus.ACCEPTED, ApplicationStatus.REJECTED},
    ApplicationStatus.ASSET_ERROR: {ApplicationStatus.QUEUED},
}


class ApplicationRecord(BaseModel):
    application_id: str
    user_id: str
    job_external_id: str
    status: ApplicationStatus = ApplicationStatus.DRAFT
    resume_markdown: str | None = None
    cover_letter_markdown: str | None = None
    submitted_at: datetime | None = None
    confirmation_ref: str | None = None


# ── Interview / Learning Schemas ──────────────────────────────────────────────

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


# ── Automation Request/Response Schemas ───────────────────────────────────────

class JobMetadata(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    role_title: str = Field(..., min_length=1, max_length=255)
    platform: str | None = Field(None, max_length=100)
    application_method: ApplicationMethod
    application_url: str | None = None
    contact_email: str | None = None
    deadline: datetime | None = None

    @model_validator(mode="after")
    def validate_method_requirements(self) -> "JobMetadata":
        if self.application_method == ApplicationMethod.EMAIL and not self.contact_email:
            raise ValueError("contact_email is required when application_method is 'email'")
        if self.application_method == ApplicationMethod.WEB_FORM and not self.application_url:
            raise ValueError("application_url is required when application_method is 'web_form'")
        return self


class ResumeAsset(BaseModel):
    version_id: uuid.UUID
    storage_url: str = Field(..., min_length=10)
    filename: str = Field(..., min_length=1, max_length=255)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Filename contains path traversal characters")
        if not v.lower().endswith(".pdf"):
            raise ValueError("Resume must be a PDF file")
        return v

    @field_validator("storage_url")
    @classmethod
    def validate_storage_url(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("storage_url must use HTTPS")
        return v


class CoverLetterAsset(BaseModel):
    version_id: uuid.UUID
    storage_url: str = Field(..., min_length=10)
    content_text: str | None = None   # Optional inline text


class GuardrailConfig(BaseModel):
    manual_approval_required: bool = False
    max_retries: int = Field(default=3, ge=1, le=10)
    priority: ApplicationPriority = ApplicationPriority.NORMAL


class ApplicationSubmitRequest(BaseModel):
    """
    Input from the Orchestrator to submit a job application.
    This is the main entry point of the entire module.
    """
    user_id: uuid.UUID
    job_id: uuid.UUID
    job_metadata: JobMetadata
    resume: ResumeAsset
    cover_letter: CoverLetterAsset | None = None
    guardrails: GuardrailConfig = Field(default_factory=GuardrailConfig)


class StatusUpdateRequest(BaseModel):
    """Manual status update (e.g., user marks they received interview)."""
    status: ApplicationStatus
    reason: str | None = Field(None, max_length=500)
    changed_by: str = "user"


class ApplicationResponse(BaseModel):
    """Full application record returned by status and submit endpoints."""
    model_config = ConfigDict(from_attributes=True)  # Allow ORM → schema conversion

    application_id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    company_name: str
    role_title: str
    platform: str | None
    method: str
    status: str
    retry_count: int
    queued_at: datetime
    applied_at: datetime | None
    confirmation_id: str | None
    celery_task_id: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationSubmitResponse(BaseModel):
    """Returned immediately when a submission is accepted (202)."""
    application_id: uuid.UUID
    status: ApplicationStatus
    tracking_url: str
    message: str = "Application queued for processing"


class ApplicationListItem(BaseModel):
    """Condensed row for list endpoints."""
    model_config = ConfigDict(from_attributes=True)

    application_id: uuid.UUID
    company_name: str
    role_title: str
    status: str
    method: str
    queued_at: datetime
    applied_at: datetime | None
    confirmation_id: str | None


class StatusHistoryItem(BaseModel):
    """Single status history entry."""
    model_config = ConfigDict(from_attributes=True)

    history_id: uuid.UUID
    from_status: str | None
    to_status: str
    reason: str | None
    changed_by: str
    created_at: datetime


# ── Standard API envelope wrappers ─────────────────────────────────────────────

class Meta(BaseModel):
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SuccessResponse(BaseModel):
    """Standard success envelope wrapping any data payload."""
    success: bool = True
    data: Any
    meta: Meta | None = None


class ErrorDetail(BaseModel):
    field: str | None = None
    issue: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = []


class ErrorResponse(BaseModel):
    """Standard error envelope returned on all failures."""
    success: bool = False
    error: ErrorBody
    meta: Meta | None = None


# ── Health check schemas ────────────────────────────────────────────────────────

class ComponentHealth(BaseModel):
    status: str   # "ok" | "degraded" | "down"
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str   # "healthy" | "degraded" | "unhealthy"
    version: str
    environment: str
    components: dict[str, ComponentHealth]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ── Celery task payload (internal) ─────────────────────────────────────────────

class TaskPayload(BaseModel):
    """Serialized payload passed to Celery tasks. Must be JSON-serializable."""
    application_id: str   # UUID as string for JSON compatibility
    user_id: str
    job_id: str
    method: str
    priority: str = "normal"
    attempt: int = 1


# ── Auth & Security Schemas ───────────────────────────────────────────────────

class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=150, pattern=r"^[a-zA-Z0-9_-]+$")
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email address")
        return v.lower().strip()


class UserLoginRequest(BaseModel):
    username_or_email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    username: str
    email: str
    is_active: bool
    mfa_enabled: bool
    roles: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def extract_role_names(cls, data: Any) -> Any:
        # If the input is an ORM user object, map role models to string names
        if hasattr(data, "roles") and not isinstance(data, dict):
            role_names = [r.name.value if hasattr(r.name, "value") else str(r.name) for r in data.roles]
            return {
                "id": data.id,
                "user_id": data.id,
                "username": data.username,
                "email": data.email,
                "is_active": data.is_active,
                "mfa_enabled": data.mfa_enabled,
                "roles": role_names,
            }
        elif isinstance(data, dict):
            roles = data.get("roles", [])
            mapped_roles = []
            for r in roles:
                if hasattr(r, "name"):
                    mapped_roles.append(r.name.value if hasattr(r.name, "value") else str(r.name))
                else:
                    mapped_roles.append(str(r))
            data["roles"] = mapped_roles
            if "id" in data and "user_id" not in data:
                data["user_id"] = data["id"]
        return data


class MfaSetupResponse(BaseModel):
    provisioning_uri: str
    backup_codes: list[str]
    secret: str


class MfaVerifyRequest(BaseModel):
    code: str = Field(None, min_length=6, max_length=6, pattern=r"^\d{6}$")
    totp_token: str | None = Field(None, min_length=6, max_length=6, description="Alias for 'code' — backward compatibility")
    # Temp session or token to verify login when MFA is enabled
    mfa_token: str | None = None

    @model_validator(mode="after")
    def normalize_code_field(self) -> "MfaVerifyRequest":
        """Accept both 'code' and 'totp_token' — normalize to 'code'."""
        if not self.code and self.totp_token:
            self.code = self.totp_token
        if not self.code:
            raise ValueError("Either 'code' or 'totp_token' must be provided (6-digit TOTP)")
        return self


class UserSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_info: str | None
    ip_address: str | None
    user_agent: str | None
    expires_at: datetime
    created_at: datetime
    revoked_at: datetime | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    requires_mfa: bool = False
    mfa_token: str | None = None
    user_id: uuid.UUID | None = None
