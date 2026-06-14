# Integration Contracts

**Author**: Member 1 — Career Orchestrator + Integration Lead  
**Version**: 1.0 | June 2026  
**Status**: Authoritative — all members must implement to these contracts

---

## Purpose

This document defines the exact input/output schema for each AI agent and each
backend service. All inter-module communication goes through these contracts.
No member may change a contract unilaterally — open a PR and get Member 1 review.

---

## Shared Types

```python
# UserId, JobId, DocumentId are all UUID strings
UserId     = str   # e.g. "a1b2c3d4-..."
JobId      = str
DocumentId = str

# Skill object (used in both CV and Job schemas)
Skill = {
    "name":  str,            # normalised lowercase, e.g. "python"
    "level": "beginner" | "intermediate" | "advanced" | "expert",
    "years": int | None,
}
```

---

## Agent Contracts

### 1. Job Scraping Agent (`FR-1`)
Owner: Member 2

**Input**
```json
{
  "keywords":         ["string"],
  "location":         "string",
  "job_type":         "full_time | part_time | internship | contract",
  "experience_level": "entry | mid | senior | any",
  "platforms":        ["linkedin", "indeed"],
  "max_results":      50
}
```

**Output**
```json
{
  "status": "success | partial | failed",
  "jobs": [
    {
      "external_id":     "string",
      "platform":        "linkedin | indeed",
      "title":           "string",
      "company_name":    "string",
      "location":        "string",
      "description":     "string",
      "required_skills": ["string"],
      "salary_min":      null,
      "salary_max":      null,
      "posted_date":     "ISO8601",
      "deadline":        "ISO8601 | null",
      "application_url": "string | null",
      "contact_email":   "string | null"
    }
  ],
  "stats":  {"linkedin": 0, "indeed": 0, "total": 0},
  "errors": ["string"]
}
```

---

### 2. Job Verification Agent (`FR-2`)
Owner: Member 2

**Input**
```json
{
  "raw_jobs": ["<RawJob objects from scraping agent>"]
}
```

**Output**
```json
{
  "status": "success",
  "verified_jobs": [
    {
      "<all RawJob fields>": "...",
      "verified_status":  "verified | unverified | rejected",
      "rejection_reason": "duplicate | expired | suspicious | null",
      "quality_score":    0.85,
      "keywords":         ["extracted", "keywords"],
      "is_active":        true
    }
  ],
  "stats": {
    "total_input":   100,
    "verified":      80,
    "rejected":      15,
    "flagged":       5
  }
}
```

---

### 3. Job Matching Agent (`FR-4`)
Owner: Member 3

**Input**
```json
{
  "user_id":    "UUID",
  "job_ids":    ["UUID"],
  "user_skills": ["<Skill objects>"],
  "user_profile": {
    "location":          "string",
    "years_experience":  3,
    "preferred_job_type": "full_time",
    "career_goals":      "string"
  }
}
```

**Output**
```json
{
  "status": "success",
  "matches": [
    {
      "job_id":              "UUID",
      "compatibility_score": 87.5,
      "breakdown": {
        "skills_match":      90.0,
        "experience_match":  85.0,
        "location_match":    100.0,
        "goals_alignment":   75.0
      },
      "matched_skills":   ["python", "django"],
      "missing_skills":   ["kubernetes"],
      "rank":             1
    }
  ]
}
```

---

### 4. Resume Optimizer Agent (`FR-5`, `FR-6`)
Owner: Member 4

**Input**
```json
{
  "user_id":  "UUID",
  "job_id":   "UUID",
  "cv_data":  "<StructuredCV>",
  "job_data": "<VerifiedJob>"
}
```

**Output**
```json
{
  "status":        "success | failed",
  "document_id":   "UUID",
  "file_path":     "s3://bucket/path/resume.pdf",
  "keywords_used": ["python", "agile"],
  "ats_score":     88.5,
  "match_summary": "string"
}
```

---

### 5. Cover Letter Agent (`FR-7`)
Owner: Member 4

**Input**
```json
{
  "user_id":      "UUID",
  "job_id":       "UUID",
  "cv_data":      "<StructuredCV>",
  "job_data":     "<VerifiedJob>",
  "company_info": {
    "name":     "string",
    "industry": "string",
    "website":  "string | null"
  }
}
```

**Output**
```json
{
  "status":      "success | failed",
  "document_id": "UUID",
  "file_path":   "s3://bucket/path/cover_letter.pdf",
  "word_count":  320,
  "tone":        "professional | conversational"
}
```

---

### 6. Application Automation Agent (`FR-8`)
Owner: Member 5

**Input**
```json
{
  "user_id":         "UUID",
  "job_id":          "UUID",
  "resume_id":       "UUID",
  "cover_letter_id": "UUID",
  "method":          "email | web_form | auto",
  "job_data": {
    "contact_email":   "string | null",
    "application_url": "string | null"
  }
}
```

**Output**
```json
{
  "status":           "submitted | failed | manual_required",
  "application_id":   "UUID",
  "method_used":      "email | web_form",
  "submitted_at":     "ISO8601",
  "confirmation_ref": "string | null",
  "failure_reason":   "string | null"
}
```

---

### 7. Skill Gap Agent (`FR-10`)
Owner: Member 3

**Input**
```json
{
  "user_id":      "UUID",
  "job_id":       "UUID",
  "user_skills":  ["<Skill objects>"],
  "job_skills":   ["string"]
}
```

**Output**
```json
{
  "status": "success",
  "analysis_id": "UUID",
  "missing_skills": [
    {
      "name":              "kubernetes",
      "priority":          "high | medium | low",
      "estimated_weeks":   8,
      "resources": [
        {"title": "string", "url": "string", "type": "course | book | tutorial"}
      ]
    }
  ],
  "roadmap_summary": "string",
  "projected_salary_uplift": "15%"
}
```

---

### 8. Interview Prep Agent (`FR-11`)
Owner: Member 6

**Input** (session start)
```json
{
  "user_id":    "UUID",
  "job_id":     "UUID",
  "job_data":   "<VerifiedJob>",
  "session_type": "technical | behavioural | mixed"
}
```

**Output** (question set)
```json
{
  "status":     "ready",
  "session_id": "UUID",
  "questions":  [
    {
      "id":         1,
      "type":       "technical | behavioural | situational",
      "question":   "string",
      "hints":      ["string"],
      "ideal_tags": ["keywords to mention"]
    }
  ]
}
```

**Input** (response evaluation)
```json
{
  "session_id": "UUID",
  "question_id": 1,
  "response_text": "string"
}
```

**Output** (feedback)
```json
{
  "score":       78.0,
  "feedback":    "string",
  "strengths":   ["string"],
  "improvements": ["string"]
}
```

---

## Backend Service Endpoints (REST)

All endpoints are prefixed `/api/v1/`.
Auth: Bearer JWT required on all except `/auth/*`.

| Method | Path | Owner | Description |
|--------|------|-------|-------------|
| POST | `/auth/register` | M1 | Create account |
| POST | `/auth/login`    | M1 | Get JWT tokens |
| POST | `/profile/cv`    | M3 | Upload + analyse CV |
| GET  | `/jobs/`         | M2 | List verified jobs |
| GET  | `/jobs/:id/match`| M3 | Compatibility score for user |
| POST | `/applications/` | M5 | Trigger application workflow |
| GET  | `/applications/` | M5 | List user applications |
| GET  | `/skill-gap/`    | M3 | Get skill gap analysis |
| POST | `/interview/sessions` | M6 | Start mock interview |

---

## Environment Variables

All members must honour these env var names. Use `.env.example` as source of truth.

```
# Databases
DATABASE_URL=postgresql://user:pass@localhost:5432/career_assistant
REDIS_URL=redis://localhost:6379
MONGODB_URI=mongodb://localhost:27017/career_assistant

# APIs
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
INDEED_API_KEY=
OPENAI_API_KEY=

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=

# Storage
AWS_S3_BUCKET=
AWS_REGION=

# Security
JWT_SECRET=
JWT_EXPIRY_MINUTES=60
```

---

## Error Handling Protocol

All agent outputs and API responses use this error envelope:

```json
{
  "success": false,
  "error": {
    "code":    "AGENT_FAILED | VALIDATION_ERROR | NOT_FOUND | RATE_LIMITED",
    "message": "human-readable string",
    "details": {}
  }
}
```

Retry policy (implemented by orchestrator):
- Rate limit (429): exponential backoff, max 3 retries
- Timeout: 30s per agent call, configurable per agent type
- Fatal errors: mark TaskResult as failed, notify user via Notification service
