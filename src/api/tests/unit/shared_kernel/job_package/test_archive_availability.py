"""Unit tests for JobPackage archive availability helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared_kernel.job_package.archive_availability import job_package_archive_exists
from shared_kernel.job_package.builder import JobPackageBuilder
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    JobPackageId,
    SyncMode,
)


def test_job_package_work_dir_defaults_to_tmp_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KARTOGRAPH_EXTRACTION_RUNTIME_JOB_PACKAGE_WORK_DIR", raising=False)

    from shared_kernel.job_package.archive_availability import job_package_work_dir

    assert job_package_work_dir() == Path("/tmp/kartograph/job_packages")


def test_job_package_archive_exists_when_file_present(tmp_path: Path) -> None:
    package_id = "01JTESTPACK0000000000000099"
    content_bytes = b"# hello\n"
    builder = JobPackageBuilder(
        data_source_id="ds-1",
        knowledge_graph_id="kg-1",
        sync_mode=SyncMode.FULL_REFRESH,
        package_id=JobPackageId(value=package_id),
    )
    ref = builder.add_content(content_bytes)
    builder.add_changeset_entry(
        ChangesetEntry(
            operation=ChangeOperation.ADD,
            id="file-1",
            type="io.kartograph.change.file",
            path="README.md",
            content_ref=ref,
            content_type="text/markdown",
            metadata={},
        )
    )
    builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
    builder.build(tmp_path)

    assert job_package_archive_exists(work_dir=tmp_path, job_package_id=package_id) is True


def test_job_package_archive_exists_when_file_missing(tmp_path: Path) -> None:
    assert job_package_archive_exists(work_dir=tmp_path, job_package_id="missing") is False
