"""Periodic scraper: fetches all configured sources and publishes listings."""
from __future__ import annotations

import asyncio
import logging

from app.adapters.aggregator import all_adapters
from app.config import get_settings
from app.pipeline import queue

log = logging.getLogger(__name__)


async def scrape_once() -> int:
    client = queue.get_redis()
    total = 0
    for adapter in all_adapters():
        try:
            listings = await adapter.fetch_jobs()
        except Exception:
            log.exception("adapter %s failed", adapter.source_name)
            continue
        for listing in listings:
            queue.publish(client, queue.SCRAPED, listing.model_dump(mode="json"))
            total += 1
        log.info("%s: published %d listings", adapter.source_name, len(listings))
    return total


async def main() -> None:
    interval = get_settings().scrape_interval_seconds
    while True:
        await scrape_once()
        await asyncio.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
