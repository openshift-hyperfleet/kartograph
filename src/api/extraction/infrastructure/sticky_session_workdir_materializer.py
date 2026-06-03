"""Prepare sticky session work directories with JobPackage materialization."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import zipfile

from extraction.domain.prepared_job_package_source import PreparedJobPackageSource
from shared_kernel.job_package.path_safety import validate_zip_entry_name
from shared_kernel.job_package.reader import JobPackageReader
from shared_kernel.job_package.value_objects import JobPackageId

_WORKSPACE_INDEX_FILENAME = "sources-index.json"


def _replace_directory(path: Path) -> None:
    """Replace a directory tree without removing its parent mount point."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


class StickySessionWorkdirMaterializer:
    """Materialize JobPackage archives into a session-scoped work directory."""

    def __init__(self, *, job_package_work_dir: Path) -> None:
        self._job_package_work_dir = job_package_work_dir

    def prepare(
        self,
        *,
        session_id: str,
        knowledge_graph_id: str,
        job_packages: tuple[PreparedJobPackageSource, ...] = (),
    ) -> Path:
        """Create or refresh the host work directory for one sticky session."""
        session_root = self._job_package_work_dir / "sticky-sessions" / session_id
        session_root.mkdir(parents=True, exist_ok=True)
        ingestion_context_dir = session_root / "ingestion-context"
        repository_files_dir = session_root / "repository-files"
        _replace_directory(ingestion_context_dir)
        _replace_directory(repository_files_dir)

        index_sources: list[dict[str, object]] = []
        for source in job_packages:
            archive_path = self._job_package_work_dir / JobPackageId(
                value=source.package_id
            ).archive_name()
            if not archive_path.exists():
                continue
            reader = JobPackageReader(archive_path)
            manifest = reader.read_manifest()
            if manifest.entry_count <= 0:
                continue

            package_dir = ingestion_context_dir / source.package_id
            package_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive_path) as archive:
                for entry_name in archive.namelist():
                    validate_zip_entry_name(entry_name)
                    archive.extract(entry_name, path=package_dir)

            repository_folder = source.repository_folder
            sample_paths: list[str] = []
            for change in reader.iter_changeset():
                if change.content_ref is None or not change.path:
                    continue
                validate_zip_entry_name(change.path)
                output_path = repository_files_dir / repository_folder / change.path
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(reader.read_content(change.content_ref))
                if len(sample_paths) < 8:
                    sample_paths.append(change.path)

            index_sources.append(
                {
                    "job_package_id": source.package_id,
                    "data_source_id": source.data_source_id,
                    "data_source_name": source.data_source_name,
                    "repository_folder": repository_folder,
                    "entry_count": manifest.entry_count,
                    "sync_mode": str(manifest.sync_mode),
                    "repository_root": f"repository-files/{repository_folder}",
                    "sample_paths": sample_paths,
                    "file_extension_counts": self._extension_counts(
                        repository_files_dir / repository_folder
                    ),
                }
            )

        marker = session_root / "knowledge-graph-id"
        marker.write_text(knowledge_graph_id, encoding="utf-8")
        self._write_workspace_index(
            session_root=session_root,
            knowledge_graph_id=knowledge_graph_id,
            sources=index_sources,
        )
        return session_root

    @staticmethod
    def _extension_counts(root: Path) -> dict[str, int]:
        """Summarize file extensions under one materialized repository folder."""
        counts: dict[str, int] = {}
        if not root.is_dir():
            return counts
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            if any(part.startswith(".") for part in file_path.parts):
                continue
            suffix = file_path.suffix.lower() or "(no extension)"
            counts[suffix] = counts.get(suffix, 0) + 1
        return dict(sorted(counts.items()))

    def _write_workspace_index(
        self,
        *,
        session_root: Path,
        knowledge_graph_id: str,
        sources: list[dict[str, object]],
    ) -> None:
        index_path = session_root / _WORKSPACE_INDEX_FILENAME
        index_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "knowledge_graph_id": knowledge_graph_id,
                    "sources": sources,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
