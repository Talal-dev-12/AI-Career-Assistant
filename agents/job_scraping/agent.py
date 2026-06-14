"""
Job Scraping Agent  (FR-1)
Owner: Member 2 — Job Discovery Lead

Integration contract (defined by Member 1):

INPUT payload:
    {
        "keywords":        list[str],   # e.g. ["software engineer", "python"]
        "location":        str,          # e.g. "Karachi, PK" or "Remote"
        "job_type":        str,          # "full_time" | "part_time" | "internship"
        "experience_level": str,         # "entry" | "mid" | "senior"
        "platforms":       list[str],    # ["linkedin", "indeed"] (default: both)
        "max_results":     int,          # per platform, default 50
    }

OUTPUT:
    {
        "status": "success" | "partial" | "failed",
        "jobs":   list[RawJob],
        "stats":  {"linkedin": int, "indeed": int, "total": int},
        "errors": list[str],   # platform-level errors, if any
    }

RawJob schema:
    {
        "external_id":    str,
        "platform":       "linkedin" | "indeed",
        "title":          str,
        "company_name":   str,
        "location":       str,
        "description":    str,
        "required_skills": list[str],
        "salary_min":     float | None,
        "salary_max":     float | None,
        "posted_date":    str,   # ISO 8601
        "deadline":       str | None,
        "application_url": str | None,
        "contact_email":  str | None,
        "raw_html":       str | None,
    }
"""

from typing import Any
from agents.base_agent import BaseAgent, AgentError


class JobScrapingAgent(BaseAgent):
    """
    Collects job listings from LinkedIn and Indeed APIs.
    Member 2 implements the body of `run`.
    """

    @property
    def agent_name(self) -> str:
        return "JobScrapingAgent"

    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self.validate_payload(payload, required_keys=["keywords", "location"])

        platforms = payload.get("platforms", ["linkedin", "indeed"])
        results = []
        errors = []
        stats = {}

        for platform in platforms:
            try:
                jobs = await self._scrape_platform(platform, payload)
                results.extend(jobs)
                stats[platform] = len(jobs)
                self.log("info", f"Scraped {len(jobs)} jobs from {platform}")
            except Exception as exc:
                errors.append(f"{platform}: {exc}")
                stats[platform] = 0
                self.log("warning", f"Platform {platform} failed: {exc}")

        if not results and errors:
            raise AgentError(f"All platforms failed: {errors}")

        stats["total"] = len(results)
        return {
            "status": "success" if not errors else "partial",
            "jobs": results,
            "stats": stats,
            "errors": errors,
        }

    async def _scrape_platform(self, platform: str, params: dict) -> list[dict]:
        """
        TODO (Member 2): Implement per-platform scraping.
        Use LinkedIn API / Indeed API credentials from environment.
        Apply exponential backoff on rate limiting (429).
        """
        raise NotImplementedError(f"_scrape_platform({platform}) not yet implemented")
