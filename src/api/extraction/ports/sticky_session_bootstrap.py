"""Port for building sticky session runtime bootstrap payloads."""

from __future__ import annotations

from typing import Protocol

from extraction.ports.runtime import StickySessionRuntimeBootstrap


class IStickySessionBootstrapBuilder(Protocol):
    """Prepare host paths and credentials for sticky session containers."""

    async def build(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        session_id: str,
        include_job_packages: bool,
    ) -> StickySessionRuntimeBootstrap | None:
        """Return bootstrap payload when container runtime is enabled."""
        ...
