"""Re-materialize missing JobPackage archives before workspace preparation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from management.infrastructure.job_package_archive_reader import SqlJobPackageArchiveReader
from shared_kernel.job_package.archive_availability import job_package_archive_exists

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobPackageArchiveHydrationResult:
    """Outcome of ensuring JobPackage ZIP archives exist on disk."""

    hydrated_count: int
    skipped_count: int
    errors: tuple[str, ...]


class JobPackageArchiveHydrator:
    """Ensure JobPackage ZIP archives exist for every data source on a knowledge graph."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        job_package_work_dir: Path,
    ) -> None:
        self._session = session
        self._job_package_work_dir = job_package_work_dir
        self._archive_reader = SqlJobPackageArchiveReader(
            session=session,
            job_package_work_dir=job_package_work_dir,
        )

    async def ensure_for_knowledge_graph(
        self,
        *,
        knowledge_graph_id: str,
        tenant_id: str,
    ) -> JobPackageArchiveHydrationResult:
        """Re-run ingest-only ingestion for data sources whose archives are missing."""
        rows = await self._load_data_sources(knowledge_graph_id=knowledge_graph_id)
        if not rows:
            return JobPackageArchiveHydrationResult(
                hydrated_count=0,
                skipped_count=0,
                errors=(),
            )

        hydrated = 0
        skipped = 0
        errors: list[str] = []
        for row in rows:
            data_source_id = str(row["id"])
            package_id = await self._archive_reader.latest_job_package_id_for_data_source(
                data_source_id=data_source_id,
            )
            if job_package_archive_exists(
                work_dir=self._job_package_work_dir,
                job_package_id=package_id,
            ):
                skipped += 1
                continue
            try:
                await self._hydrate_data_source(
                    row=row,
                    knowledge_graph_id=knowledge_graph_id,
                    tenant_id=tenant_id,
                )
                hydrated += 1
            except Exception as exc:  # noqa: BLE001
                name = str(row.get("name") or data_source_id)
                message = f"{name}: {exc}"
                logger.exception(
                    "job_package_archive_hydration_failed data_source_id=%s kg_id=%s",
                    data_source_id,
                    knowledge_graph_id,
                )
                errors.append(message)

        if hydrated:
            logger.info(
                "job_package_archives_hydrated kg_id=%s hydrated=%s skipped=%s",
                knowledge_graph_id,
                hydrated,
                skipped,
            )
        return JobPackageArchiveHydrationResult(
            hydrated_count=hydrated,
            skipped_count=skipped,
            errors=tuple(errors),
        )

    async def _load_data_sources(self, *, knowledge_graph_id: str) -> list[dict[str, Any]]:
        result = await self._session.execute(
            text(
                """
                SELECT
                  id,
                  name,
                  adapter_type,
                  connection_config,
                  credentials_path,
                  clone_head_commit,
                  last_prepared_commit
                FROM data_sources
                WHERE knowledge_graph_id = :knowledge_graph_id
                ORDER BY name
                """
            ),
            {"knowledge_graph_id": knowledge_graph_id},
        )
        rows: list[dict[str, Any]] = []
        for row in result.fetchall():
            connection_config = row.connection_config or {}
            if not isinstance(connection_config, dict):
                connection_config = dict(connection_config)
            rows.append(
                {
                    "id": str(row.id),
                    "name": str(row.name or ""),
                    "adapter_type": str(row.adapter_type or ""),
                    "connection_config": connection_config,
                    "credentials_path": row.credentials_path,
                    "clone_head_commit": row.clone_head_commit,
                    "last_prepared_commit": row.last_prepared_commit,
                }
            )
        return rows

    async def _hydrate_data_source(
        self,
        *,
        row: dict[str, Any],
        knowledge_graph_id: str,
        tenant_id: str,
    ) -> None:
        from infrastructure.outbox.repository import OutboxRepository
        from infrastructure.settings import get_management_settings
        from ingestion.application.services.ingestion_service import IngestionService
        from ingestion.infrastructure.adapters.github import GitHubAdapter
        from management.infrastructure.repositories.fernet_secret_store import FernetSecretStore

        data_source_id = str(row["id"])
        adapter_type = str(row["adapter_type"])
        credentials_path = row.get("credentials_path")
        credentials: dict[str, str] = {}
        if credentials_path:
            mgmt_settings = get_management_settings()
            encryption_keys = [
                key.strip()
                for key in mgmt_settings.encryption_key.get_secret_value().split(",")
                if key.strip()
            ]
            if not encryption_keys:
                raise RuntimeError("No encryption keys configured for credential retrieval")
            credential_reader = FernetSecretStore(
                session=self._session,
                encryption_keys=encryption_keys,
            )
            credentials = await credential_reader.retrieve(
                path=str(credentials_path),
                tenant_id=tenant_id,
            )

        ingestion_service = IngestionService(
            adapter_registry={"github": GitHubAdapter()},
            work_dir=self._job_package_work_dir,
        )
        sync_run_id = str(ULID())
        ingestion_result = await ingestion_service.run(
            sync_run_id=sync_run_id,
            data_source_id=data_source_id,
            knowledge_graph_id=knowledge_graph_id,
            adapter_type=adapter_type,
            connection_config=dict(row.get("connection_config") or {}),
            credentials_path=str(credentials_path) if credentials_path else None,
            tenant_id=tenant_id,
            credentials=credentials,
            baseline_commit=row.get("clone_head_commit") or row.get("last_prepared_commit"),
            pipeline_mode="ingest_only",
        )
        if ingestion_result.entry_count <= 0:
            raise RuntimeError(
                "Ingestion produced an empty JobPackage; verify data source connectivity"
            )

        now = datetime.now(UTC)
        outbox = OutboxRepository(session=self._session)
        await outbox.append(
            event_type="IngestionPrepared",
            payload={
                "sync_run_id": sync_run_id,
                "data_source_id": data_source_id,
                "knowledge_graph_id": knowledge_graph_id,
                "job_package_id": str(ingestion_result.job_package_id),
                "prepared_commit_sha": ingestion_result.prepared_commit_sha,
                "prepared_file_count": ingestion_result.branch_file_count,
                "changeset_entry_count": ingestion_result.entry_count,
                "occurred_at": now.isoformat(),
                "hydrated": True,
            },
            occurred_at=now,
            aggregate_type="sync_run",
            aggregate_id=sync_run_id,
        )
        await self._session.execute(
            text(
                """
                UPDATE data_sources
                SET
                  last_prepared_commit = :prepared_commit,
                  last_prepared_file_count = :prepared_file_count,
                  clone_head_commit = COALESCE(:prepared_commit, clone_head_commit),
                  updated_at = :updated_at
                WHERE id = :data_source_id
                """
            ),
            {
                "data_source_id": data_source_id,
                "prepared_commit": ingestion_result.prepared_commit_sha,
                "prepared_file_count": ingestion_result.branch_file_count,
                "updated_at": now,
            },
        )
        await self._session.commit()
