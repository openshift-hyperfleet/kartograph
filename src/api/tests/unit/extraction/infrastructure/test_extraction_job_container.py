"""Unit tests for extraction job container lifecycle helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from extraction.infrastructure.extraction_job_container import (
    extraction_job_container_name,
    stop_extraction_job_container,
    stop_extraction_job_containers,
)


def test_extraction_job_container_name_is_stable_and_short() -> None:
    name = extraction_job_container_name("Adapter Deep Extraction_batch_0005_f46f3c66")

    assert name.startswith("kartograph-extract-")
    assert len(name) <= 63


@patch("extraction.infrastructure.extraction_job_container.create_container_runtime")
def test_stop_extraction_job_containers_stops_each_job(mock_create_runtime: MagicMock) -> None:
    runtime = MagicMock()
    runtime.remove_by_name.side_effect = [True, False]
    mock_create_runtime.return_value = runtime

    stopped = stop_extraction_job_containers(
        job_ids=("job-a", "job-b"),
        container_engine="docker",
    )

    assert stopped == 1
    assert runtime.remove_by_name.call_count == 2
    runtime.remove_by_name.assert_any_call(
        extraction_job_container_name("job-a"),
        force=True,
    )


@patch("extraction.infrastructure.extraction_job_container.create_container_runtime")
def test_stop_extraction_job_container_delegates_to_runtime(mock_create_runtime: MagicMock) -> None:
    runtime = MagicMock()
    runtime.remove_by_name.return_value = True
    mock_create_runtime.return_value = runtime

    assert stop_extraction_job_container(job_id="job-a", container_engine="docker") is True
