"""Port for polling sticky session agent runtime health."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol


class IStickyRuntimeHealthChecker(Protocol):
    """Poll agent runtime /health until the sticky container is ready."""

    def wait_until_healthy(
        self,
        *,
        runtime_base_url: str,
        timeout_seconds: float = 90.0,
    ) -> AsyncIterator[str]:
        """Yield human-readable progress lines until healthy or timeout."""
        ...

    async def is_healthy(self, *, runtime_base_url: str) -> bool:
        """Return whether the sticky runtime currently responds on /health."""
        ...
