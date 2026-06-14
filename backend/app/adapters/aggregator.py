"""Adzuna aggregator adapter.

STUB: activates only when ADZUNA_APP_ID / ADZUNA_APP_KEY are configured.
Sign up at https://developer.adzuna.com/ (free tier available).
"""
from __future__ import annotations

import httpx

from app.adapters.base import JobSourceAdapter
from app.config import get_settings
from app.models.schemas import JobListing, JobSource

API = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"


class AdzunaAdapter(JobSourceAdapter):
    source_name = "aggregator"

    def __init__(self, what: str = "software engineer", country: str = "gb"):
        self.what = what
        self.country = country

    async def fetch_jobs(self) -> list[JobListing]:
        settings = get_settings()
        if not (settings.adzuna_app_id and settings.adzuna_app_key):
            return []  # credentials not configured - adapter disabled
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                API.format(country=self.country),
                params={
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "what": self.what,
                    "results_per_page": 50,
                },
            )
            resp.raise_for_status()
            return [
                JobListing(
                    external_id=f"adzuna:{r['id']}",
                    source=JobSource.AGGREGATOR,
                    title=r.get("title", ""),
                    company=(r.get("company") or {}).get("display_name", "unknown"),
                    location=(r.get("location") or {}).get("display_name"),
                    url=r.get("redirect_url", ""),
                    description=r.get("description", ""),
                )
                for r in resp.json().get("results", [])
            ]


def all_adapters() -> list[JobSourceAdapter]:
    """Factory wiring every configured source."""
    from app.adapters.greenhouse import GreenhouseAdapter
    from app.adapters.lever import LeverAdapter

    settings = get_settings()
    adapters: list[JobSourceAdapter] = []
    if settings.greenhouse_board_list:
        adapters.append(GreenhouseAdapter(settings.greenhouse_board_list))
    if settings.lever_company_list:
        adapters.append(LeverAdapter(settings.lever_company_list))
    adapters.append(AdzunaAdapter())
    return adapters
