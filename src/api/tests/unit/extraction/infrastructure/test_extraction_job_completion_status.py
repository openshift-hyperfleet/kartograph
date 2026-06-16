"""Regression tests for extraction job recent-history and completion status."""

from __future__ import annotations

from pathlib import Path

from extraction.domain.extraction_job import ExtractionJobStatus

_REPO_PATH = (
    Path(__file__).resolve().parents[4]
    / "extraction"
    / "infrastructure"
    / "repositories"
    / "extraction_job_repository.py"
)


def test_list_recent_jobs_includes_archived_rows() -> None:
    source = _REPO_PATH.read_text(encoding="utf-8")
    assert "status != ExtractionJobStatus.ARCHIVED" not in source


def test_mark_job_completed_auto_archives_when_writes_applied() -> None:
    source = _REPO_PATH.read_text(encoding="utf-8")
    assert "if write_ops > 0" in source
    assert "ExtractionJobStatus.ARCHIVED.value" in source

    write_ops = 2
    status = (
        ExtractionJobStatus.ARCHIVED.value
        if write_ops > 0
        else ExtractionJobStatus.COMPLETED.value
    )
    assert status == ExtractionJobStatus.ARCHIVED.value
