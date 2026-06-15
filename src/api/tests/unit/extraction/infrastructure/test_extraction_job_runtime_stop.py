"""Unit tests for extraction job runtime teardown (containers + OpenShell sandboxes)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from extraction.infrastructure.extraction_job_container import stop_extraction_job_runtimes


@patch("extraction.infrastructure.extraction_job_container.stop_extraction_job_sandboxes")
@patch("extraction.infrastructure.extraction_job_container.stop_extraction_job_containers")
def test_stop_extraction_job_runtimes_stops_sandboxes_on_openshell_backend(
    mock_stop_containers: MagicMock,
    mock_stop_sandboxes: MagicMock,
) -> None:
    mock_stop_containers.return_value = 0
    mock_stop_sandboxes.return_value = 3

    containers, sandboxes = stop_extraction_job_runtimes(
        job_ids=("job-a", "job-b"),
        openshell_backend=True,
    )

    assert containers == 0
    assert sandboxes == 3
    mock_stop_sandboxes.assert_called_once_with(job_ids=("job-a", "job-b"), sweep_orphans=True)


@patch("extraction.infrastructure.extraction_job_container.stop_extraction_job_sandboxes")
@patch("extraction.infrastructure.extraction_job_container.stop_extraction_job_containers")
def test_stop_extraction_job_runtimes_skips_sandboxes_for_container_backend(
    mock_stop_containers: MagicMock,
    mock_stop_sandboxes: MagicMock,
) -> None:
    mock_stop_containers.return_value = 2

    containers, sandboxes = stop_extraction_job_runtimes(
        job_ids=("job-a",),
        openshell_backend=False,
    )

    assert containers == 2
    assert sandboxes == 0
    mock_stop_sandboxes.assert_not_called()
