"""Materialize per-job workspaces for agentic-ci extraction runs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from extraction.domain.extraction_job import ExtractionJobRecord, ExtractionTargetFile
from extraction.domain.prepared_job_package_source import PreparedJobPackageSource
from extraction.infrastructure.prepared_job_package_reader import SqlPreparedJobPackageReader
from extraction.infrastructure.workload_runtime_settings import ExtractionWorkloadRuntimeSettings
from extraction.ports.runtime import ScopedWorkloadCredentials
from shared_kernel.job_package.path_safety import validate_zip_entry_name
from shared_kernel.job_package.reader import JobPackageReader
from shared_kernel.job_package.value_objects import JobPackageId


class ExtractionJobWorkdirMaterializer:
    """Prepare a host work directory for one extraction job container run."""

    def __init__(
        self,
        *,
        settings: ExtractionWorkloadRuntimeSettings,
        prepared_job_package_reader: SqlPreparedJobPackageReader,
    ) -> None:
        self._settings = settings
        self._prepared_job_package_reader = prepared_job_package_reader
        self._job_package_work_dir = Path(settings.job_package_work_dir)

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
        repository_files_dir = job_root / "repository-files"
        repository_files_dir.mkdir(parents=True, exist_ok=True)

        job_packages = await self._prepared_job_package_reader.list_latest_for_knowledge_graph(
            knowledge_graph_id=job.knowledge_graph_id,
        )
        packages_by_id = {source.package_id: source for source in job_packages}
        if job.target_files:
            self._materialize_target_files(
                repository_files_dir=repository_files_dir,
                target_files=job.target_files,
                packages_by_id=packages_by_id,
            )
        else:
            self._materialize_all_repository_files(
                repository_files_dir=repository_files_dir,
                job_packages=job_packages,
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
        }
        (job_root / "job-context.json").write_text(
            json.dumps(context, indent=2),
            encoding="utf-8",
        )
        return job_root

    def _materialize_all_repository_files(
        self,
        *,
        repository_files_dir: Path,
        job_packages: tuple[PreparedJobPackageSource, ...],
    ) -> None:
        for source in job_packages:
            archive_path = self._job_package_work_dir / JobPackageId(
                value=source.package_id
            ).archive_name()
            if not archive_path.is_file():
                continue
            reader = JobPackageReader(archive_path)
            for change in reader.iter_changeset():
                if change.content_ref is None or not change.path:
                    continue
                validate_zip_entry_name(change.path)
                output_path = repository_files_dir / source.repository_folder / change.path
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(reader.read_content(change.content_ref))

    def _materialize_target_files(
        self,
        *,
        repository_files_dir: Path,
        target_files: tuple[ExtractionTargetFile, ...],
        packages_by_id: dict[str, PreparedJobPackageSource],
    ) -> None:
        for target_file in target_files:
            source = packages_by_id.get(target_file.package_id)
            if source is None:
                continue
            archive_path = self._job_package_work_dir / JobPackageId(
                value=source.package_id
            ).archive_name()
            if not archive_path.is_file():
                continue
            reader = JobPackageReader(archive_path)
            for change in reader.iter_changeset():
                if change.path != target_file.path or change.content_ref is None:
                    continue
                validate_zip_entry_name(change.path)
                output_path = repository_files_dir / source.repository_folder / change.path
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(reader.read_content(change.content_ref))
                break
