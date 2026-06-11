"""Filesystem runtime context preparation for extraction workloads."""

from __future__ import annotations

from pathlib import Path
import zipfile

from extraction.ports.services import ExtractionRuntimeContext
from shared_kernel.job_package.path_safety import validate_zip_entry_name
from shared_kernel.job_package.reader import JobPackageReader
from shared_kernel.job_package.value_objects import JobPackageId


class FilesystemExtractionRuntimeContextBuilder:
    """Prepare runtime directories from JobPackage archives."""

    def __init__(self, *, work_dir: Path) -> None:
        self._work_dir = work_dir

    def build(self, *, sync_run_id: str, job_package_id: str) -> ExtractionRuntimeContext:
        package_id = JobPackageId(value=job_package_id)
        archive_path = self._work_dir / package_id.archive_name()
        reader = JobPackageReader(archive_path)

        run_root = self._work_dir / "extraction-runtimes" / sync_run_id
        ingestion_context_dir = run_root / "ingestion-context"
        repository_files_dir = run_root / "repository-files"
        ingestion_context_dir.mkdir(parents=True, exist_ok=True)
        repository_files_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(archive_path) as archive:
            for entry_name in archive.namelist():
                validate_zip_entry_name(entry_name)
                archive.extract(entry_name, path=ingestion_context_dir)

        # Materialize repository-style files for agent-friendly traversal.
        for change in reader.iter_changeset():
            if change.content_ref is None or not change.path:
                continue
            validate_zip_entry_name(change.path)
            output_path = repository_files_dir / change.path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(reader.read_content(change.content_ref))

        return ExtractionRuntimeContext(
            ingestion_context_dir=str(ingestion_context_dir),
            repository_files_dir=str(repository_files_dir),
            job_package_archive=str(archive_path),
        )
