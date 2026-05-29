"""Health polling for sticky session agent runtime containers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx


class StickyRuntimeHealthChecker:
    """Poll agent runtime /health until the sticky container is ready."""

    def __init__(self, *, request_timeout_seconds: float = 3.0) -> None:
        self._request_timeout_seconds = request_timeout_seconds

    async def wait_until_healthy(
        self,
        *,
        runtime_base_url: str,
        timeout_seconds: float = 90.0,
        poll_interval_seconds: float = 1.0,
    ) -> AsyncIterator[str]:
        """Yield human-readable progress lines until healthy or timeout."""
        if runtime_base_url.startswith("memory://"):
            yield "In-memory assistant runtime ready"
            return

        deadline = asyncio.get_event_loop().time() + timeout_seconds
        url = f"{runtime_base_url.rstrip('/')}/health"
        attempt = 0
        while asyncio.get_event_loop().time() < deadline:
            attempt += 1
            yield f"Waiting for assistant container health check (attempt {attempt})…"
            try:
                async with httpx.AsyncClient(timeout=self._request_timeout_seconds) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        yield "Assistant container is healthy"
                        return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(poll_interval_seconds)

        raise TimeoutError(
            f"Sticky session runtime did not become healthy within {int(timeout_seconds)}s"
        )
