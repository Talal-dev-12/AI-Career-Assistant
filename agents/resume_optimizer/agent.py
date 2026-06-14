"""
Resume Optimizer Agent  (FR-5, FR-6)
Owner: Member 4 — Document Generation Lead

Integration contract (defined by Member 1):

INPUT payload:
    {
        "user_id":  str,
        "job_id":   str,
        "cv_data":  dict,   # structured CV extracted by CVAnalyser
        "job_data": dict,   # verified job record from Job service
    }

    cv_data schema:
        {
            "personal": {"name": str, "email": str, "phone": str, "location": str},
            "summary":  str,
            "skills":   list[{"name": str, "level": str, "years": int}],
            "experience": list[{
                "title": str, "company": str, "start": str, "end": str,
                "bullets": list[str],
            }],
            "education": list[{"degree": str, "institution": str, "year": int}],
            "certifications": list[str],
            "projects": list[{"name": str, "description": str, "tech": list[str]}],
        }

    job_data schema: (subset of RawJob + verification data)
        {
            "title": str,
            "company_name": str,
            "description": str,
            "required_skills": list[str],
            "nice_to_have_skills": list[str],
            "keywords": list[str],   # extracted by verification agent
        }

OUTPUT:
    {
        "status":       "success" | "failed",
        "document_id":  str,         # ID for Generated_Documents table
        "file_path":    str,         # PDF path in cloud storage
        "keywords_used": list[str],  # ATS keywords incorporated
        "ats_score":    float,       # 0–100
        "match_summary": str,        # 1-sentence human-readable summary
    }

CONSTRAINTS (from SRS Section 7.3):
    - NEVER invent skills, experience, or credentials not in cv_data
    - Only reorganise and reframe existing information
    - Output must be ATS-compatible (no graphics, standard headings)
    - Keyword inclusion ≥ 80% of job description keywords (NFR 5.3)
"""

from typing import Any
from agents.base_agent import BaseAgent, AgentError


class ResumeOptimizerAgent(BaseAgent):

    @property
    def agent_name(self) -> str:
        return "ResumeOptimizerAgent"

    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self.validate_payload(
            payload, required_keys=["user_id", "job_id", "cv_data", "job_data"]
        )

        cv_data  = payload["cv_data"]
        job_data = payload["job_data"]

        # Step 1: Extract job keywords
        keywords = self._extract_keywords(job_data)

        # Step 2: Score and rank cv sections by relevance
        ranked = self._rank_sections(cv_data, keywords)

        # Step 3: Rewrite bullets to align with keywords (no fabrication)
        optimised = self._rewrite_bullets(ranked, keywords)

        # Step 4: Render to PDF
        document_id, file_path = await self._render_pdf(
            optimised, payload["user_id"], payload["job_id"]
        )

        # Step 5: Calculate ATS score
        ats_score = self._ats_score(optimised, keywords)

        return {
            "status": "success",
            "document_id": document_id,
            "file_path": file_path,
            "keywords_used": [k for k in keywords if self._keyword_present(k, optimised)],
            "ats_score": ats_score,
            "match_summary": f"Resume optimised for {job_data['title']} at {job_data['company_name']}",
        }

    def _extract_keywords(self, job_data: dict) -> list[str]:
        """TODO (Member 4): Use NLP/LLM to extract ranked keywords from description."""
        return job_data.get("keywords", []) + job_data.get("required_skills", [])

    def _rank_sections(self, cv_data: dict, keywords: list[str]) -> dict:
        """TODO (Member 4): Score each CV section against keywords, return ranked copy."""
        raise NotImplementedError

    def _rewrite_bullets(self, cv_data: dict, keywords: list[str]) -> dict:
        """TODO (Member 4): Reframe bullets using LLM to include keywords — no new facts."""
        raise NotImplementedError

    async def _render_pdf(self, cv_data: dict, user_id: str, job_id: str) -> tuple[str, str]:
        """TODO (Member 4): Render ATS-safe PDF, upload to cloud storage, return (id, path)."""
        raise NotImplementedError

    def _ats_score(self, cv_data: dict, keywords: list[str]) -> float:
        """TODO (Member 4): Calculate keyword coverage score 0–100."""
        raise NotImplementedError

    def _keyword_present(self, keyword: str, cv_data: dict) -> bool:
        """Check if a keyword appears anywhere in the rendered cv_data."""
        text = str(cv_data).lower()
        return keyword.lower() in text
