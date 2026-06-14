"""Redis Streams event bus connecting pipeline stages.

Streams:
  jobs.scraped   -> consumed by verification worker
  jobs.verified  -> consumed by matching worker
  docs.requested -> consumed by document-generation worker

Consumer groups give at-least-once delivery; handlers are idempotent
(keyed on external_id / application_id).
"""
from __future__ import annotations

import json
from collections.abc import Callable

import redis

from app.config import get_settings

SCRAPED = "jobs.scraped"
VERIFIED = "jobs.verified"
DOCS_REQUESTED = "docs.requested"
APPROVED = "apps.approved"
WEBFORM = "apps.webform"

MAX_RETRIES = 3


def get_redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def publish(client: redis.Redis, stream: str, payload: dict) -> str:
    return client.xadd(stream, {"data": json.dumps(payload, default=str)})


def ensure_group(client: redis.Redis, stream: str, group: str) -> None:
    try:
        client.xgroup_create(stream, group, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def consume(
    client: redis.Redis,
    stream: str,
    group: str,
    consumer: str,
    handler: Callable[[dict], None],
    block_ms: int = 5000,
) -> int:
    """Read one batch, run handler per message, ack on success.

    Failed messages stay pending; after MAX_RETRIES they are acked and
    parked in <stream>.dlq. Returns number of successfully handled messages.
    """
    ensure_group(client, stream, group)
    entries = client.xreadgroup(group, consumer, {stream: ">"}, count=10, block=block_ms)
    handled = 0
    for _, messages in entries or []:
        for msg_id, fields in messages:
            payload = json.loads(fields["data"])
            try:
                handler(payload)
                client.xack(stream, group, msg_id)
                handled += 1
            except Exception as exc:  # retry via pending list, then DLQ
                retries = int(client.hincrby(f"{stream}.retries", msg_id, 1))
                if retries >= MAX_RETRIES:
                    client.xadd(f"{stream}.dlq", {"data": fields["data"], "error": str(exc)})
                    client.xack(stream, group, msg_id)
                    client.hdel(f"{stream}.retries", msg_id)
    return handled
