"""Redis is optional infrastructure. Unset REDIS_URL means the dependency is disabled."""

from __future__ import annotations


class RedisGateway:
    def __init__(self, url: str | None):
        self.url = url

    async def ping(self) -> str:
        if not self.url:
            return "disabled"
        from redis.asyncio import Redis

        client = Redis.from_url(self.url, socket_connect_timeout=1)
        try:
            await client.ping()
            return "ok"
        finally:
            await client.aclose()
