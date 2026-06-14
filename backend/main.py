import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.db.database import init_db, get_session
from app.db.models import Job
from app.api.main import app as talha_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize database models
    init_db()
    
    # 2. Create local uploads folder if it doesn't exist
    os.makedirs("uploads", exist_ok=True)
    
    # 3. Seed default jobs if database is empty
    db = next(get_session())
    try:
        existing_jobs = db.execute(select(Job)).scalars().all()
        if not existing_jobs:
            test_jobs = [
                Job(
                    external_id="job-1",
                    source="greenhouse",
                    title="Senior React Developer",
                    company="Vercel",
                    company_name="Vercel",
                    location="Remote (US)",
                    url="https://vercel.com/careers",
                    description="We are looking for a Senior React Developer to join our core framework team. You will work on optimizing Next.js rendering, building highly interactive developer consoles, and improving bundle performance. The ideal candidate has deep knowledge of React internals, server components, and modern frontend architectures.",
                    verified=True,
                    required_skills=["React", "Next.js", "TypeScript", "Frontend Architecture", "Web Performance"]
                ),
                Job(
                    external_id="job-2",
                    source="lever",
                    title="Software Engineer - Frontend",
                    company="Stripe",
                    company_name="Stripe",
                    location="Remote / NYC",
                    url="https://stripe.com/careers",
                    description="Join the dashboard team at Stripe to build beautiful, highly accessible financial tools. You will implement robust frontend payment systems, manage complex state architectures, and ensure top-tier performance for millions of active merchants worldwide.",
                    verified=True,
                    required_skills=["React", "TypeScript", "State Management", "CSS", "Accessibility"]
                ),
                Job(
                    external_id="job-3",
                    source="greenhouse",
                    title="Frontend Engineer",
                    company="Supabase",
                    company_name="Supabase",
                    location="Remote",
                    url="https://supabase.com/careers",
                    description="Looking for a Frontend Engineer to help us build the best open-source Firebase alternative. You will collaborate on the dashboard console, manage database visualizer interfaces, and build high-quality web experiences.",
                    verified=True,
                    required_skills=["React", "TypeScript", "SQL", "Database Design", "Open Source"]
                )
            ]
            for job in test_jobs:
                db.add(job)
            db.commit()
            print("Successfully seeded initial jobs.")
    except Exception as e:
        print(f"Failed to seed jobs during startup: {e}")
        
    yield

app = FastAPI(
    title="AI Career Assistant Unified API Gateway",
    description="HEllo WOrld Talla",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes from core codebase
app.include_router(talha_app.router)


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "AI Career Assistant Unified API Gateway",
        "endpoints": [
            "/users",
            "/jobs",
            "/skill-gap/analyze",
            "/interview/start",
            "/interview/{session_id}/answer"
        ]
    }
