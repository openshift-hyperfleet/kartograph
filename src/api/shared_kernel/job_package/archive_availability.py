"""Helpers for checking JobPackage archive presence on disk."""

from __future__ import annotations

import os
from pathlib import Path

from shared_kernel.job_package.value_objects import JobPackageId


def job_package_work_dir() -> Path:
    """Return the configured on-disk directory for JobPackage ZIP archives."""
    return Path(
        os.getenv(
            "KARTOGRAPH_EXTRACTION_RUNTIME_JOB_PACKAGE_WORK_DIR",
            "/tmp/kartograph/job_packages",
        )
    )


def job_package_archive_path(*, work_dir: Path, job_package_id: str) -> Path:
    """Return the expected on-disk path for one JobPackage archive."""
    return work_dir / JobPackageId(value=job_package_id).archive_name()


def job_package_archive_exists(*, work_dir: Path, job_package_id: str | None) -> bool:
    """Return whether the JobPackage ZIP archive exists locally."""
    if not job_package_id or not job_package_id.strip():
        return False
    return job_package_archive_path(work_dir=work_dir, job_package_id=job_package_id).is_file()
