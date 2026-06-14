"""Greenhouse public job-board API adapter (no auth required).

Docs: https://developers.greenhouse.io/job-board.html
"""
from __future__ import annotations

import html
import re
from datetime import datetime

import httpx

from app.adapters.base import JobSourceAdapter
from app.models.schemas import JobListing, JobSource

API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", html.unescape(text or "")).strip()


class GreenhouseAdapter(JobSourceAdapter):
    source_name = "greenhouse"

    def __init__(self, board_tokens: list[str], client: httpx.AsyncClient | None = None):
        self.board_tokens = board_tokens
        self._client = client

    async def fetch_jobs(self) -> list[JobListing]:
        listings: list[JobListing] = []
        client = self._client or httpx.AsyncClient(timeout=30)
        owns_client = self._client is None
        try:
            for board in self.board_tokens:
                resp = await client.get(API.format(board=board))
                resp.raise_for_status()
                for job in resp.json().get("jobs", []):
                    posted = job.get("updated_at")
                    listings.append(
                        JobListing(
                            external_id=f"greenhouse:{board}:{job['id']}",
                            source=JobSource.GREENHOUSE,
                            title=job.get("title", ""),
                            company=board,
                            location=(job.get("location") or {}).get("name"),
                            url=job.get("absolute_url", ""),
                            description=_strip_html(job.get("content", ""))[:20000],
                            posted_at=datetime.fromisoformat(posted) if posted else None,
                        )
                    )
        finally:
            if owns_client:
                await client.aclose()
        return listings
