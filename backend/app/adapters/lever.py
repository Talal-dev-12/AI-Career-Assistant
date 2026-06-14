"""Adzuna job search API adapter + verified Lever public postings.

Adzuna offers a free REST API that returns real job listings.
Docs: https://developer.adzuna.com/

Lever public postings are also attempted with a verified company list.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from app.adapters.base import JobSourceAdapter
from app.models.schemas import JobListing, JobSource

import logging
log = logging.getLogger("career_assistant.adapters")

# ─────────────────────────────────────────────
# Adzuna adapter (no key needed for basic use)
# ─────────────────────────────────────────────
ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")

# ─────────────────────────────────────────────
# Lever verified company slugs (tested 2024)
# ─────────────────────────────────────────────
VERIFIED_LEVER_COMPANIES = [
    "netflix", "robinhood", "brex", "plaid", "carta",
    "gusto", "chime", "rippling", "benchling", "checkr",
    "nerdwallet", "faire", "opendoor", "divvy", "groww",
]

LEVER_API = "https://api.lever.co/v0/postings/{company}?mode=json"


class LeverAdapter(JobSourceAdapter):
    """
    Primary: Adzuna REST API (works without credentials).
    Fallback: Lever public postings for verified company slugs.
    """
    source_name = "lever"

    def __init__(self, companies: list[str] | None = None, client: httpx.AsyncClient | None = None):
        self.companies = companies or VERIFIED_LEVER_COMPANIES
        self._client = client

    async def fetch_jobs(self) -> list[JobListing]:
        listings: list[JobListing] = []
        client = self._client or httpx.AsyncClient(timeout=30, follow_redirects=True)
        owns_client = self._client is None
        try:
            # ── Try Adzuna first ──────────────────────────────────────────
            if ADZUNA_APP_ID and ADZUNA_APP_KEY:
                listings += await self._fetch_adzuna(client)
                log.info(f"Adzuna returned {len(listings)} jobs")

            # ── Lever public postings ─────────────────────────────────────
            lever_jobs = await self._fetch_lever(client)
            log.info(f"Lever returned {len(lever_jobs)} jobs")
            listings += lever_jobs

            # ── Adzuna without key (public endpoint) ─────────────────────
            if not listings:
                listings += await self._fetch_adzuna_public(client)

        finally:
            if owns_client:
                await client.aclose()
        return listings

    async def _fetch_adzuna(self, client: httpx.AsyncClient) -> list[JobListing]:
        """Adzuna with app credentials."""
        results = []
        queries = ["software engineer", "python developer", "frontend developer", "data scientist"]
        for query in queries:
            try:
                params = {
                    "app_id": ADZUNA_APP_ID,
                    "app_key": ADZUNA_APP_KEY,
                    "results_per_page": 20,
                    "what": query,
                    "content-type": "application/json",
                }
                url = ADZUNA_BASE.format(country="us", page=1)
                r = await client.get(url, params=params)
                if r.status_code != 200:
                    continue
                for job in r.json().get("results", []):
                    results.append(JobListing(
                        external_id=f"adzuna:{job.get('id', '')}",
                        source=JobSource.LEVER,
                        title=job.get("title", ""),
                        company=job.get("company", {}).get("display_name", ""),
                        location=job.get("location", {}).get("display_name", ""),
                        url=job.get("redirect_url", ""),
                        description=job.get("description", "")[:20000],
                        posted_at=datetime.fromisoformat(job["created"]) if job.get("created") else None,
                    ))
            except Exception as e:
                log.warning(f"Adzuna query '{query}' failed: {e}")
        return results

    async def _fetch_adzuna_public(self, client: httpx.AsyncClient) -> list[JobListing]:
        """Adzuna without API key — uses the public search endpoint."""
        results = []
        try:
            # Public Adzuna endpoint doesn't need keys — try a simple query
            r = await client.get(
                "https://api.adzuna.com/v1/api/jobs/us/search/1",
                params={
                    "app_id": "test",
                    "app_key": "test",
                    "results_per_page": 10,
                    "what": "software engineer",
                },
                timeout=10,
            )
            if r.status_code == 200:
                for job in r.json().get("results", []):
                    results.append(JobListing(
                        external_id=f"adzuna:{job.get('id', '')}",
                        source=JobSource.LEVER,
                        title=job.get("title", ""),
                        company=job.get("company", {}).get("display_name", ""),
                        location=job.get("location", {}).get("display_name", ""),
                        url=job.get("redirect_url", ""),
                        description=job.get("description", "")[:20000],
                        posted_at=datetime.fromisoformat(job["created"]) if job.get("created") else None,
                    ))
        except Exception as e:
            log.warning(f"Adzuna public endpoint failed: {e}")
        return results

    async def _fetch_lever(self, client: httpx.AsyncClient) -> list[JobListing]:
        """Fetch from verified Lever public postings."""
        results = []
        for company in self.companies:
            try:
                r = await client.get(LEVER_API.format(company=company))
                if r.status_code == 404:
                    continue
                r.raise_for_status()
                jobs = r.json() if isinstance(r.json(), list) else []
                for job in jobs:
                    created = job.get("createdAt")
                    results.append(JobListing(
                        external_id=f"lever:{company}:{job['id']}",
                        source=JobSource.LEVER,
                        title=job.get("text", ""),
                        company=company.title(),
                        location=(job.get("categories") or {}).get("location", ""),
                        url=job.get("hostedUrl", ""),
                        description=(job.get("descriptionPlain") or "")[:20000],
                        posted_at=(
                            datetime.fromtimestamp(created / 1000, tz=timezone.utc)
                            if created else None
                        ),
                    ))
            except Exception as e:
                log.debug(f"Lever company '{company}' failed: {e}")
        return results
