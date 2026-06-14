"""Lever public postings API adapter (no auth required).

Docs: https://github.com/lever/postings-api
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.adapters.base import JobSourceAdapter
from app.models.schemas import JobListing, JobSource

API = "https://api.lever.co/v0/postings/{company}?mode=json"


class LeverAdapter(JobSourceAdapter):
    source_name = "lever"

    def __init__(self, companies: list[str], client: httpx.AsyncClient | None = None):
        self.companies = companies
        self._client = client

    async def fetch_jobs(self) -> list[JobListing]:
        listings: list[JobListing] = []
        client = self._client or httpx.AsyncClient(timeout=30)
        owns_client = self._client is None
        try:
            for company in self.companies:
                resp = await client.get(API.format(company=company))
                resp.raise_for_status()
                for job in resp.json():
                    created = job.get("createdAt")
                    listings.append(
                        JobListing(
                            external_id=f"lever:{company}:{job['id']}",
                            source=JobSource.LEVER,
                            title=job.get("text", ""),
                            company=company,
                            location=(job.get("categories") or {}).get("location"),
                            url=job.get("hostedUrl", ""),
                            description=(job.get("descriptionPlain") or "")[:20000],
                            posted_at=(
                                datetime.fromtimestamp(created / 1000, tz=timezone.utc)
                                if created
                                else None
                            ),
                        )
                    )
        finally:
            if owns_client:
                await client.aclose()
        return listings
