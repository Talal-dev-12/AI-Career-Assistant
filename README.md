# AI Career Assistant

An intelligent multi-agent platform that automates the job search and application process for students and professionals.

## Architecture

```
┌──────────────────────────── Frontend Layer ─────────────────────────────┐
│  Dashboard │ CV Upload │ Job Browser │ Resume Preview │ Tracker │ Prep  │
│                      Authentication Module                               │
└──────────────────────────────────┬──────────────────────────────────────┘
                                REST API
┌──────────────────────────── Backend Layer ──────────────────────────────┐
│                           API Gateway                                   │
│  Job Svc │ User Profile │ Application Svc │ Notification │ Orchestrator │
│              PostgreSQL · Redis · MongoDB · Elasticsearch               │
└──────────────────────────────────┬──────────────────────────────────────┘
                              Agent Tasks
┌──────────────────────────── AI Agent Layer ─────────────────────────────┐
│  Job Scraping → Verification → Matching → Resume Optimizer              │
│                                         → Cover Letter                  │
│                                         → App Automation               │
│  Skill Gap Analysis │ Interview Prep │ Profile Maintenance              │
└──────────────────────────────────┬──────────────────────────────────────┘
                               API Calls
┌──────────────────────────── External Services ──────────────────────────┐
│  LinkedIn API │ Indeed API │ OpenAI API │ Gmail/SMTP │ Selenium         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
ai-career-assistant/
├── frontend/               # React web application
│   └── src/
│       ├── components/     # UI components by feature
│       ├── pages/          # Route-level page components
│       ├── hooks/          # Custom React hooks
│       ├── services/       # API client calls
│       └── store/          # State management (Redux/Zustand)
│
├── backend/                # Node.js / FastAPI backend
│   ├── api_gateway/        # Request routing, rate limiting, auth
│   ├── services/           # Business logic services
│   │   ├── auth/           # Registration, login, MFA, tokens
│   │   ├── job/            # Job CRUD, search, filtering
│   │   ├── profile/        # User profile and CV management
│   │   ├── application/    # Application submission and tracking
│   │   ├── notification/   # Email and push notifications
│   │   └── ai_orchestrator/ # Dispatches tasks to AI agents
│   ├── models/             # Database models / schemas
│   ├── db/                 # Migrations and seed data
│   ├── middleware/         # Auth, logging, error handling
│   └── utils/              # Shared utilities
│
├── agents/                 # AI agent modules (Python)
│   ├── job_scraping/       # FR-1: Collect jobs from LinkedIn, Indeed
│   ├── job_verification/   # FR-2: Dedup, fraud detection, expiry
│   ├── job_matching/       # FR-4: Compatibility scoring
│   ├── resume_optimizer/   # FR-5, FR-6: ATS-optimized resume
│   ├── cover_letter/       # FR-7: Personalized cover letters
│   ├── skill_gap/          # FR-10: Gap analysis and roadmaps
│   ├── interview_prep/     # FR-11: Mock interviews and feedback
│   ├── app_automation/     # FR-8: Email and web form submission
│   └── profile_maintenance/ # FR-12: Continuous profile updates
│
├── tests/
│   ├── unit/               # Unit tests per module
│   ├── integration/        # Service-to-service tests
│   └── e2e/                # End-to-end user workflow tests
│
├── docs/                   # Architecture docs, API specs, ADRs
└── scripts/                # DB setup, deployment, data seeds
```

## Quick Start

### Prerequisites
- Node.js 20+
- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15, Redis 7, MongoDB 6

### Setup

```bash
# Clone and enter repo
git clone https://github.com/your-team/ai-career-assistant.git
cd ai-career-assistant

# Copy environment files
cp .env.example .env

# Start all services with Docker
docker compose up -d

# Backend
cd backend && npm install && npm run dev

# Frontend
cd frontend && npm install && npm run dev

# Agents (Python)
cd agents && pip install -r requirements.txt
python -m job_scraping.main   # or run via orchestrator
```

## Team Roles and Ownership

| Member | Role | Owns |
|--------|------|------|
| 1 | Career Orchestrator + Repo & Spec Lead | Architecture, `ai_orchestrator/`, integration contracts |
| 2 | Job Discovery Lead | `agents/job_scraping/`, `agents/job_verification/`, `backend/services/job/` |
| 3 | Profile & Matching Lead | `agents/job_matching/`, `agents/skill_gap/`, `backend/services/profile/` |
| 4 | Document Generation Lead | `agents/resume_optimizer/`, `agents/cover_letter/` |
| 5 | Application & Tracking Lead | `agents/app_automation/`, `backend/services/application/`, `frontend/src/components/tracker/` |
| 6 | Interview Prep Lead | `agents/interview_prep/`, `frontend/src/components/interview/` |

## Contributing

- Branch from `develop`: `feature/<your-feature-name>`
- All PRs require review from Member 1 (integration lead) before merge
- Run `npm test` and `pytest` before pushing
- See `docs/CONTRIBUTING.md` for full guidelines

## SRS Reference

Full requirements: `docs/SRS_v1.0.md`

Key non-functionals:
- Response time: job search < 3s, resume gen < 30s
- Availability: 99.5% uptime
- Security: AES-256 at rest, TLS 1.3 in transit, MFA support
- Scale: 1,000 concurrent users, 100,000 active users
