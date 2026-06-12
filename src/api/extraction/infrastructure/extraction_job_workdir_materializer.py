"""Materialize per-job workspaces for agentic-ci extraction runs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from extraction.domain.extraction_job import ExtractionJobRecord
from extraction.domain.observability.extraction_job_probe import (
    ExtractionJobMaterializationObservation,
    ExtractionJobProbe,
    LoggingExtractionJobProbe,
)
from extraction.domain.prepared_job_package_source import PreparedJobPackageSource
from extraction.infrastructure.extraction_job_repository_files import (
    RepositoryFilesMaterializationResult,
    collect_instance_repository_paths,
    materialize_all_repository_files,
    materialize_instance_repository_paths,
    materialize_target_files,
    write_sources_index,
)
from extraction.infrastructure.extraction_job_workdir_layout import prepare_agentic_ci_workspace
from extraction.infrastructure.prepared_job_package_reader import SqlPreparedJobPackageReader
from infrastructure.job_packages.archive_hydrator import JobPackageArchiveHydrator
from extraction.infrastructure.workload_runtime_settings import ExtractionWorkloadRuntimeSettings
from extraction.ports.runtime import ScopedWorkloadCredentials


class ExtractionJobWorkdirMaterializer:
    """Prepare a host work directory for one extraction job container run."""

    def __init__(
        self,
        *,
        settings: ExtractionWorkloadRuntimeSettings,
        prepared_job_package_reader: SqlPreparedJobPackageReader,
        probe: ExtractionJobProbe | None = None,
        archive_hydrator: JobPackageArchiveHydrator | None = None,
    ) -> None:
        self._settings = settings
        self._prepared_job_package_reader = prepared_job_package_reader
        self._job_package_work_dir = Path(settings.job_package_work_dir)
        self._probe = probe or LoggingExtractionJobProbe()
        self._archive_hydrator = archive_hydrator

    async def prepare(
        self,
        *,
        job: ExtractionJobRecord,
        tenant_id: str,
        credentials: ScopedWorkloadCredentials,
    ) -> Path:
        job_root = Path(self._settings.extraction_job_work_dir) / job.knowledge_graph_id / job.job_id
        if job_root.exists():
            shutil.rmtree(job_root)
        job_root.mkdir(parents=True, exist_ok=True)
        repository_files_dir = job_root / "repository-files"
        repository_files_dir.mkdir(parents=True, exist_ok=True)

        hydration_warnings: list[str] = []
        if self._archive_hydrator is not None:
            hydration = await self._archive_hydrator.ensure_for_knowledge_graph(
                knowledge_graph_id=job.knowledge_graph_id,
                tenant_id=tenant_id,
            )
            hydration_warnings.extend(hydration.errors)

        job_packages = await self._prepared_job_package_reader.list_latest_for_knowledge_graph(
            knowledge_graph_id=job.knowledge_graph_id,
        )
        packages_by_id = {source.package_id: source for source in job_packages}
        materialization = self._materialize_repository_files(
            job=job,
            repository_files_dir=repository_files_dir,
            job_packages=job_packages,
            packages_by_id=packages_by_id,
        )
        if hydration_warnings:
            materialization = materialization.merge(
                RepositoryFilesMaterializationResult(
                    warnings=tuple(hydration_warnings),
                )
            )
        write_sources_index(
            job_root=job_root,
            knowledge_graph_id=job.knowledge_graph_id,
            job_packages=job_packages,
            materialization=materialization,
        )
        prepare_agentic_ci_workspace(
            job_root,
            container_run_uid=self._settings.container_run_uid,
            container_run_gid=self._settings.container_run_gid,
        )
        self._probe.repository_files_materialized(
            ExtractionJobMaterializationObservation(
                job_id=job.job_id,
                knowledge_graph_id=job.knowledge_graph_id,
                files_written=materialization.files_written,
                packages_requested=materialization.packages_requested,
                packages_missing=materialization.packages_missing,
                paths_requested=materialization.paths_requested,
                warnings=materialization.warnings,
            )
        )

        context = {
            "tenant_id": tenant_id,
            "knowledge_graph_id": job.knowledge_graph_id,
            "job_id": job.job_id,
            "job_set_name": job.job_set_name,
            "strategy": job.strategy,
            "description": job.description,
            "api_base_url": self._settings.api_base_url.rstrip("/"),
            "workload_token": credentials.token,
            "target_instances": [instance.to_dict() for instance in job.target_instances],
            "target_files": [target_file.to_dict() for target_file in job.target_files],
            "repository_files": materialization.to_dict(),
        }
        (job_root / "job-context.json").write_text(
            json.dumps(context, indent=2) + "\n",
            encoding="utf-8",
        )
        return job_root

    def _materialize_repository_files(
        self,
        *,
        job: ExtractionJobRecord,
        repository_files_dir: Path,
        job_packages: tuple[PreparedJobPackageSource, ...],
        packages_by_id: dict[str, PreparedJobPackageSource],
    ) -> RepositoryFilesMaterializationResult:
        if job.target_files:
            return materialize_target_files(
                repository_files_dir=repository_files_dir,
                job_package_work_dir=self._job_package_work_dir,
                target_files=job.target_files,
                packages_by_id=packages_by_id,
            )

        materialization = RepositoryFilesMaterializationResult()
        if job.target_instances:
            instance_paths = collect_instance_repository_paths(job.target_instances)
            if instance_paths:
                materialization = materialize_instance_repository_paths(
                    repository_files_dir=repository_files_dir,
                    job_package_work_dir=self._job_package_work_dir,
                    job_packages=job_packages,
                    paths=instance_paths,
                )
            if materialization.files_written == 0:
                fallback = materialize_all_repository_files(
                    repository_files_dir=repository_files_dir,
                    job_package_work_dir=self._job_package_work_dir,
                    job_packages=job_packages,
                )
                materialization = materialization.merge(fallback)
            return materialization

        return materialize_all_repository_files(
            repository_files_dir=repository_files_dir,
            job_package_work_dir=self._job_package_work_dir,
            job_packages=job_packages,
        )
