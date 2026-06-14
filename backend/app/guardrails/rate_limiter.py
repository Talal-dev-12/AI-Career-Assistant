"""Tool guardrail: Redis-backed daily application cap per user+platform."""
from datetime import datetime, timezone

import redis

from app.config import get_settings


class RateLimitExceeded(Exception):
    pass


class ApplicationRateLimiter:
    def __init__(self, client: redis.Redis | None = None, daily_cap: int | None = None):
        settings = get_settings()
        self.client = client or redis.Redis.from_url(settings.redis_url)
        self.daily_cap = daily_cap or settings.daily_application_cap

    def _key(self, user_id: str, platform: str) -> str:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"appcap:{user_id}:{platform}:{today}"

    def check_and_increment(self, user_id: str, platform: str) -> int:
        """Atomically increment; raise if over cap. Returns count used today."""
        key = self._key(user_id, platform)
        count = self.client.incr(key)
        if count == 1:
            self.client.expire(key, 60 * 60 * 24)
        if count > self.daily_cap:
            raise RateLimitExceeded(
                f"Daily cap of {self.daily_cap} applications reached for {platform}"
            )
        return int(count)
