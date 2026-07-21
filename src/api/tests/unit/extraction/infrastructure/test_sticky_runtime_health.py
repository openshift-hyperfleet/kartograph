"""Unit tests for sticky runtime health checking of non-HTTP runtime URLs."""

from __future__ import annotations

import pytest

from extraction.infrastructure.sticky_runtime_health import StickyRuntimeHealthChecker


class TestStickyRuntimeHealthChecker:
    @pytest.mark.asyncio
    async def test_local_agent_url_is_always_healthy(self) -> None:
        checker = StickyRuntimeHealthChecker()

        assert await checker.is_healthy(runtime_base_url="local-agent://req-123")

    @pytest.mark.asyncio
    async def test_memory_url_is_always_healthy(self) -> None:
        checker = StickyRuntimeHealthChecker()

        assert await checker.is_healthy(runtime_base_url="memory://sticky-runtime")

    @pytest.mark.asyncio
    async def test_wait_until_healthy_returns_immediately_for_local_agent(
        self,
    ) -> None:
        checker = StickyRuntimeHealthChecker()

        lines = [
            line
            async for line in checker.wait_until_healthy(
                runtime_base_url="local-agent://req-123",
                timeout_seconds=5.0,
            )
        ]

        assert lines == ["Local agent Sandbox runtime ready"]
