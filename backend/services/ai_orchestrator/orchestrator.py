"""
AI Orchestrator Service
Member 1 — Career Orchestrator + Integration Lead

Central dispatcher that receives task requests from the backend and routes them
to the appropriate AI agent. Handles agent chaining, error propagation, and
result aggregation.

Agent execution order for primary workflow:
  CV Upload
    └─► CVAnalysisAgent
          └─► (parallel) JobScrapingAgent + JobVerificationAgent
                └─► JobMatchingAgent
                      ├─► ResumeOptimizerAgent ──┐
                      ├─► CoverLetterAgent        ├─► AppAutomationAgent
                      └─► SkillGapAgent (side)    │
                                                  └─► ApplicationTracker
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AgentTask(str, Enum):
    """All dispatchable agent task types, mapped to SRS functional requirements."""
    SCRAPE_JOBS        = "scrape_jobs"         # FR-1
    VERIFY_JOBS        = "verify_jobs"          # FR-2
    ANALYSE_CV         = "analyse_cv"           # FR-3
    MATCH_JOBS         = "match_jobs"           # FR-4
    OPTIMISE_RESUME    = "optimise_resume"      # FR-5, FR-6
    GENERATE_COVER     = "generate_cover"       # FR-7
    SUBMIT_APPLICATION = "submit_application"   # FR-8
    ANALYSE_SKILL_GAP  = "analyse_skill_gap"    # FR-10
    MOCK_INTERVIEW     = "mock_interview"        # FR-11
    UPDATE_PROFILE     = "update_profile"       # FR-12


@dataclass
class TaskRequest:
    task: AgentTask
    user_id: str
    payload: dict[str, Any]
    priority: int = 5          # 1 (highest) – 10 (lowest)
    correlation_id: str = ""   # for tracing a full workflow chain


@dataclass
class TaskResult:
    task: AgentTask
    user_id: str
    success: bool
    data: dict[str, Any]
    error: str | None = None
    correlation_id: str = ""


class AIOrchestrator:
    """
    Routes TaskRequests to the correct agent and handles chaining.

    Usage:
        orchestrator = AIOrchestrator()
        result = await orchestrator.dispatch(TaskRequest(
            task=AgentTask.ANALYSE_CV,
            user_id="user-123",
            payload={"cv_path": "/uploads/cv.pdf"},
        ))
    """

    def __init__(self) -> None:
        # Import agents lazily to avoid circular deps and allow
        # each module to be developed independently
        self._registry: dict[AgentTask, str] = {
            AgentTask.SCRAPE_JOBS:        "agents.job_scraping.agent.JobScrapingAgent",
            AgentTask.VERIFY_JOBS:        "agents.job_verification.agent.JobVerificationAgent",
            AgentTask.ANALYSE_CV:         "agents.profile_maintenance.cv_analyser.CVAnalyser",
            AgentTask.MATCH_JOBS:         "agents.job_matching.agent.JobMatchingAgent",
            AgentTask.OPTIMISE_RESUME:    "agents.resume_optimizer.agent.ResumeOptimizerAgent",
            AgentTask.GENERATE_COVER:     "agents.cover_letter.agent.CoverLetterAgent",
            AgentTask.SUBMIT_APPLICATION: "agents.app_automation.agent.AppAutomationAgent",
            AgentTask.ANALYSE_SKILL_GAP:  "agents.skill_gap.agent.SkillGapAgent",
            AgentTask.MOCK_INTERVIEW:     "agents.interview_prep.agent.InterviewPrepAgent",
            AgentTask.UPDATE_PROFILE:     "agents.profile_maintenance.agent.ProfileMaintenanceAgent",
        }

    async def dispatch(self, request: TaskRequest) -> TaskResult:
        """Dispatch a single task to the appropriate agent."""
        logger.info(
            "Dispatching task=%s user=%s correlation=%s",
            request.task, request.user_id, request.correlation_id,
        )
        agent = self._load_agent(request.task)
        try:
            data = await agent.run(request.payload)
            return TaskResult(
                task=request.task,
                user_id=request.user_id,
                success=True,
                data=data,
                correlation_id=request.correlation_id,
            )
        except Exception as exc:
            logger.exception("Agent %s failed: %s", request.task, exc)
            return TaskResult(
                task=request.task,
                user_id=request.user_id,
                success=False,
                data={},
                error=str(exc),
                correlation_id=request.correlation_id,
            )

    async def run_application_workflow(
        self,
        user_id: str,
        job_id: str,
        correlation_id: str,
    ) -> dict[str, TaskResult]:
        """
        Orchestrate the full application workflow for a single job:
          1. Resume optimisation  ─┐ (parallel)
          2. Cover letter gen      ─┘
          3. Application submission
          4. Skill gap analysis    (non-blocking side task)

        Returns a dict keyed by AgentTask.
        """
        results: dict[str, TaskResult] = {}
        base = {"user_id": user_id, "job_id": job_id}

        # Step 1 & 2 — parallel document generation
        resume_task = TaskRequest(
            task=AgentTask.OPTIMISE_RESUME,
            user_id=user_id,
            payload=base,
            correlation_id=correlation_id,
        )
        cover_task = TaskRequest(
            task=AgentTask.GENERATE_COVER,
            user_id=user_id,
            payload=base,
            correlation_id=correlation_id,
        )
        resume_result, cover_result = await asyncio.gather(
            self.dispatch(resume_task),
            self.dispatch(cover_task),
        )
        results[AgentTask.OPTIMISE_RESUME] = resume_result
        results[AgentTask.GENERATE_COVER] = cover_result

        if not resume_result.success or not cover_result.success:
            logger.error("Document generation failed — aborting submission")
            return results

        # Step 3 — submit application
        submission_payload = {
            **base,
            "resume_id": resume_result.data.get("document_id"),
            "cover_letter_id": cover_result.data.get("document_id"),
        }
        submit_result = await self.dispatch(TaskRequest(
            task=AgentTask.SUBMIT_APPLICATION,
            user_id=user_id,
            payload=submission_payload,
            correlation_id=correlation_id,
        ))
        results[AgentTask.SUBMIT_APPLICATION] = submit_result

        # Step 4 — skill gap analysis (fire and forget, non-blocking)
        asyncio.create_task(self.dispatch(TaskRequest(
            task=AgentTask.ANALYSE_SKILL_GAP,
            user_id=user_id,
            payload=base,
            priority=8,
            correlation_id=correlation_id,
        )))

        return results

    async def run_job_discovery_workflow(
        self,
        search_params: dict[str, Any],
        correlation_id: str,
    ) -> TaskResult:
        """
        Scrape → verify pipeline.
        Scraping agent output feeds directly into verification.
        """
        scrape_result = await self.dispatch(TaskRequest(
            task=AgentTask.SCRAPE_JOBS,
            user_id="system",
            payload=search_params,
            correlation_id=correlation_id,
        ))
        if not scrape_result.success:
            return scrape_result

        return await self.dispatch(TaskRequest(
            task=AgentTask.VERIFY_JOBS,
            user_id="system",
            payload={"raw_jobs": scrape_result.data.get("jobs", [])},
            correlation_id=correlation_id,
        ))

    # ── private ──────────────────────────────────────────────────────────

    def _load_agent(self, task: AgentTask):
        """Dynamically import and instantiate the agent class for a task."""
        import importlib
        module_path, class_name = self._registry[task].rsplit(".", 1)
        module = importlib.import_module(module_path)
        agent_class = getattr(module, class_name)
        return agent_class()
