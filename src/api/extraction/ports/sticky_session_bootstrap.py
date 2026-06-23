"""Port for building sticky session runtime bootstrap payloads."""

from __future__ import annotations

from typing import Protocol

from extraction.domain.prepared_job_package_source import PreparedJobPackageSource
from extraction.ports.runtime import StickySessionRuntimeBootstrap


class IStickySessionBootstrapBuilder(Protocol):
    """Prepare host paths and credentials for sticky session containers."""

    async def resolve_job_packages(
        self,
        *,
        knowledge_graph_id: str,
        include_job_packages: bool,
    ) -> tuple[PreparedJobPackageSource, ...]:
        """Return JobPackage snapshots that would be materialized for one session."""
        ...

    async def build(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        session_id: str,
        include_job_packages: bool,
        ui_mode: str | None = None,
    ) -> StickySessionRuntimeBootstrap | None:
        """Return bootstrap payload when container runtime is enabled."""
        ...
