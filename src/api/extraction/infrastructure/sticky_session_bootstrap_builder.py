"""Build sticky session runtime bootstrap payloads for container launch."""

from __future__ import annotations

from extraction.infrastructure.sticky_session_workdir_materializer import (
    StickySessionWorkdirMaterializer,
)
from extraction.infrastructure.workload_runtime import ScopedWorkloadCredentialIssuer
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
    get_extraction_workload_runtime_settings,
)
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
    ) -> None:
        self._credential_issuer = credential_issuer
        self._prepared_job_package_reader = prepared_job_package_reader
        self._workdir_materializer = workdir_materializer
        self._runtime_settings = runtime_settings or get_extraction_workload_runtime_settings()

    async def resolve_job_package_ids(
        self,
        *,
        knowledge_graph_id: str,
        include_job_packages: bool,
    ) -> tuple[str, ...]:
        """Return JobPackage IDs that would be materialized for one session."""
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
    ) -> StickySessionRuntimeBootstrap | None:
        if self._runtime_settings.backend != "container":
            return None

        package_ids: tuple[str, ...] = ()
        if include_job_packages:
            package_ids = await self._prepared_job_package_reader.list_latest_for_knowledge_graph(
                knowledge_graph_id=knowledge_graph_id,
            )
        host_session_work_dir = self._workdir_materializer.prepare(
            session_id=session_id,
            knowledge_graph_id=knowledge_graph_id,
            job_package_ids=package_ids,
        )
        credentials = self._credential_issuer.issue_for_sticky_session(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
        )
        return StickySessionRuntimeBootstrap(
            tenant_id=tenant_id,
            credentials=credentials,
            host_session_work_dir=str(host_session_work_dir),
            host_skills_dir=self._runtime_settings.skills_dir,
            api_base_url=self._runtime_settings.api_base_url,
        )