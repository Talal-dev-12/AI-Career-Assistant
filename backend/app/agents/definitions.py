"""OpenAI Agents SDK agent definitions.

Manager + handoff hybrid: CareerOrchestrator owns the session and hands off
to specialists. Every specialist returns a structured Pydantic output_type.
"""
from agents import Agent

from app.agents.tools import (
    calculate_match_score,
    generate_learning_roadmap,
    parse_cv,
    send_application_email,
    submit_web_application,
    verify_company,
)
from app.models.schemas import (
    CoverLetter,
    LearningRoadmap,
    MatchScore,
    ResumeDiff,
    UserProfile,
    VerifiedJob,
)

SPECIALIST_MODEL = "gpt-4o-mini"
ORCHESTRATOR_MODEL = "gpt-4o"

profile_agent = Agent(
    name="ProfileAgent",
    instructions=(
        "Extract a structured profile from PII-scrubbed CV text: skills, experience "
        "entries, education, locations, target roles. Extract only what is present; "
        "never infer skills not explicitly stated."
    ),
    model=SPECIALIST_MODEL,
    tools=[parse_cv],
    output_type=UserProfile,
)

job_verification_agent = Agent(
    name="JobVerificationAgent",
    instructions=(
        "Assess a job listing: (1) duplicate of an already-seen listing? (2) expired? "
        "(3) suspicious (pay-to-apply, crypto-only contact, vague company)? Use "
        "verify_company. Set verified_status=false with reasons when in doubt."
    ),
    model=SPECIALIST_MODEL,
    tools=[verify_company],
    output_type=VerifiedJob,
)

job_matching_agent = Agent(
    name="JobMatchingAgent",
    instructions=(
        "Score compatibility (0-100) between the user profile and a VERIFIED job. "
        "Start from calculate_match_score baseline, then adjust for seniority fit, "
        "location, and goal alignment. List skill_overlap and missing_skills, give a "
        "one-sentence rationale. Never score unverified jobs."
    ),
    model=SPECIALIST_MODEL,
    tools=[calculate_match_score],
    output_type=MatchScore,
)

resume_agent = Agent(
    name="ResumeOptimizationAgent",
    instructions=(
        "Reorganize and emphasize existing CV content to match the job. HARD RULE: "
        "never invent skills, titles, employers, dates, or achievements. Output "
        "ATS-safe Markdown: no images, tables, columns, or HTML. List every factual "
        "claim you used in source_claims - each will be verified against the profile."
    ),
    model=SPECIALIST_MODEL,
    output_type=ResumeDiff,
)

cover_letter_agent = Agent(
    name="CoverLetterAgent",
    instructions=(
        "Write a concise, personalized cover letter (<=300 words) referencing the "
        "company and role. Use only facts from the profile; list them in "
        "source_claims for verification. Professional tone, no cliches."
    ),
    model=SPECIALIST_MODEL,
    output_type=CoverLetter,
)

application_agent = Agent(
    name="ApplicationAutomationAgent",
    instructions=(
        "Submit USER-APPROVED applications only. Prefer send_application_email when a "
        "contact address exists; otherwise report that web-form submission is pending. "
        "Capture confirmation references. Never exceed the platform rate limit."
    ),
    model=SPECIALIST_MODEL,
    tools=[send_application_email, submit_web_application],
)

skill_gap_interview_agent = Agent(
    name="SkillGapInterviewAgent",
    instructions=(
        "Two modes. (1) Skill gap: from accumulated missing_skills across the user's "
        "applications, build a prioritized learning roadmap with concrete free "
        "resources and weekly estimates. (2) Mock interview: ask realistic questions "
        "for the target role one at a time, then score each answer 0-10 with specific, "
        "actionable feedback."
    ),
    model=ORCHESTRATOR_MODEL,
    tools=[generate_learning_roadmap],
    output_type=LearningRoadmap,
)

career_orchestrator = Agent(
    name="CareerOrchestrator",
    instructions=(
        "Entry point for the career pipeline. Maintain user profile context across "
        "stages: profile parsing -> job verification -> matching -> document "
        "generation -> (user approval) -> application -> tracking -> skill "
        "development. Hand off to the matching specialist for stage work; never "
        "perform document generation yourself. Applications require explicit user "
        "approval before submission - no exceptions."
    ),
    model=ORCHESTRATOR_MODEL,
    handoffs=[
        profile_agent,
        job_verification_agent,
        job_matching_agent,
        resume_agent,
        cover_letter_agent,
        application_agent,
        skill_gap_interview_agent,
    ],
)
