from abc import ABC, abstractmethod

from app.models.schemas import JobListing


class JobSourceAdapter(ABC):
    """Pluggable interface for legitimate job sources.

    Deliberately NOT LinkedIn/Indeed scraping: both violate platform ToS and
    are brittle. Implementations target public, sanctioned job-board APIs.
    """

    source_name: str

    @abstractmethod
    async def fetch_jobs(self) -> list[JobListing]:
        """Return current open listings for this source."""
