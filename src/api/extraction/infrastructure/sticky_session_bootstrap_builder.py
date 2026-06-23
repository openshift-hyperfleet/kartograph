"""Build sticky session runtime bootstrap payloads for container launch."""

from __future__ import annotations

from infrastructure.job_packages.archive_hydrator import JobPackageArchiveHydrator
from extraction.infrastructure.sticky_session_workdir_materializer import (
    StickySessionWorkdirMaterializer,
)
from extraction.infrastructure.workload_credential_issuer import (
    ScopedWorkloadCredentialIssuer,
)
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
    get_extraction_workload_runtime_settings,
)
from extraction.domain.prepared_job_package_source import PreparedJobPackageSource
from extraction.ports.prepared_job_packages import IPreparedJobPackageReader
from extraction.ports.runtime import StickySessionRuntimeBootstrap


class StickySessionBootstrapBuilder:
    """Prepare host workdirs and credentials for sticky session containers."""

    def __init__(
        self,
        *,
        credential_issuer: ScopedWorkloadCredentialIssuer,
        prepared_job_package_reader: IPreparedJobPackageReader,
        workdir_materializer: StickySessionWorkdirMaterializer,
        runtime_settings: ExtractionWorkloadRuntimeSettings | None = None,
        archive_hydrator: JobPackageArchiveHydrator | None = None,
    ) -> None:
        self._credential_issuer = credential_issuer
        self._prepared_job_package_reader = prepared_job_package_reader
        self._workdir_materializer = workdir_materializer
        self._runtime_settings = (
            runtime_settings or get_extraction_workload_runtime_settings()
        )
        self._archive_hydrator = archive_hydrator

    async def resolve_job_packages(
        self,
        *,
        knowledge_graph_id: str,
        include_job_packages: bool,
    ) -> tuple[PreparedJobPackageSource, ...]:
        """Return JobPackage snapshots that would be materialized for one session."""
        if not include_job_packages:
            return ()
        return await self._prepared_job_package_reader.list_latest_for_knowledge_graph(
            knowledge_graph_id=knowledge_graph_id,
        )

    async def build(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        session_id: str,
        include_job_packages: bool,
        ui_mode: str | None = None,
    ) -> StickySessionRuntimeBootstrap | None:
        if self._runtime_settings.backend not in {"container", "openshell"}:
            return None

        job_packages: tuple[PreparedJobPackageSource, ...] = ()
        if include_job_packages:
            if self._archive_hydrator is not None:
                await self._archive_hydrator.ensure_for_knowledge_graph(
                    knowledge_graph_id=knowledge_graph_id,
                    tenant_id=tenant_id,
                )
            job_packages = (
                await self._prepared_job_package_reader.list_latest_for_knowledge_graph(
                    knowledge_graph_id=knowledge_graph_id,
                )
            )
        host_session_work_dir = self._workdir_materializer.prepare(
            session_id=session_id,
            knowledge_graph_id=knowledge_graph_id,
            job_packages=job_packages,
        )
        credentials = self._credential_issuer.issue_for_sticky_session(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
            session_id=session_id,
        )
        return StickySessionRuntimeBootstrap(
            tenant_id=tenant_id,
            credentials=credentials,
            host_session_work_dir=str(host_session_work_dir),
            api_base_url=self._runtime_settings.sandbox_reachable_api_base_url(),
            ui_mode=ui_mode,
        )
