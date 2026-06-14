import httpx
import pytest
import respx

from app.adapters.greenhouse import GreenhouseAdapter
from app.adapters.lever import LeverAdapter
from app.models.schemas import JobSource


@pytest.mark.asyncio
@respx.mock
async def test_greenhouse_adapter_parses_jobs():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 42,
                        "title": "Backend Engineer",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/42",
                        "location": {"name": "Remote"},
                        "content": "<p>Build &amp; ship APIs</p>",
                        "updated_at": "2026-06-01T00:00:00+00:00",
                    }
                ]
            },
        )
    )
    async with httpx.AsyncClient() as client:
        jobs = await GreenhouseAdapter(["acme"], client=client).fetch_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.external_id == "greenhouse:acme:42"
    assert job.source == JobSource.GREENHOUSE
    assert job.location == "Remote"
    assert "Build & ship APIs" in job.description  # HTML stripped


@pytest.mark.asyncio
@respx.mock
async def test_lever_adapter_parses_jobs():
    respx.get("https://api.lever.co/v0/postings/acme?mode=json").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "abc",
                    "text": "Data Engineer",
                    "hostedUrl": "https://jobs.lever.co/acme/abc",
                    "categories": {"location": "Berlin"},
                    "descriptionPlain": "ETL pipelines",
                    "createdAt": 1717200000000,
                }
            ],
        )
    )
    async with httpx.AsyncClient() as client:
        jobs = await LeverAdapter(["acme"], client=client).fetch_jobs()
    assert jobs[0].external_id == "lever:acme:abc"
    assert jobs[0].company == "acme"
    assert jobs[0].posted_at is not None
