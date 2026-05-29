"""Prepare sticky session work directories with JobPackage materialization."""

from __future__ import annotations

from pathlib import Path
import shutil
import zipfile

from shared_kernel.job_package.path_safety import validate_zip_entry_name
from shared_kernel.job_package.reader import JobPackageReader
from shared_kernel.job_package.value_objects import JobPackageId


class StickySessionWorkdirMaterializer:
    """Materialize JobPackage archives into a session-scoped work directory."""

    def __init__(self, *, job_package_work_dir: Path) -> None:
        self._job_package_work_dir = job_package_work_dir

    def prepare(
        self,
        *,
        session_id: str,
        knowledge_graph_id: str,
        job_package_ids: tuple[str, ...] = (),
    ) -> Path:
        """Create or refresh the host work directory for one sticky session."""
        session_root = self._job_package_work_dir / "sticky-sessions" / session_id
        if session_root.exists():
            shutil.rmtree(session_root)
        ingestion_context_dir = session_root / "ingestion-context"
        repository_files_dir = session_root / "repository-files"
        ingestion_context_dir.mkdir(parents=True, exist_ok=True)
        repository_files_dir.mkdir(parents=True, exist_ok=True)

        discovered = (
            self._discover_job_package_ids()
            if job_package_ids is None
            else job_package_ids
        )
        for package_id in discovered:
            archive_path = self._job_package_work_dir / JobPackageId(value=package_id).archive_name()
            if not archive_path.exists():
                continue
            package_dir = ingestion_context_dir / package_id
            package_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive_path) as archive:
                for entry_name in archive.namelist():
                    validate_zip_entry_name(entry_name)
                    archive.extract(entry_name, path=package_dir)

            reader = JobPackageReader(archive_path)
            for change in reader.iter_changeset():
                if change.content_ref is None or not change.path:
                    continue
                validate_zip_entry_name(change.path)
                output_path = repository_files_dir / package_id / change.path
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(reader.read_content(change.content_ref))

        marker = session_root / "knowledge-graph-id"
        marker.write_text(knowledge_graph_id, encoding="utf-8")
        return session_root

    def _discover_job_package_ids(self) -> tuple[str, ...]:
        package_ids: list[str] = []
        for archive in sorted(self._job_package_work_dir.glob("job-package-*.zip")):
            stem = archive.stem.removeprefix("job-package-")
            if stem:
                package_ids.append(stem)
        return tuple(package_ids)
