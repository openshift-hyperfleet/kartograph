"""Unit tests for extraction job workdir materialization."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

from datetime import UTC, datetime

import pytest

from extraction.domain.extraction_job import (
    ExtractionJobRecord,
    ExtractionJobStatus,
    ExtractionTargetInstance,
)
from extraction.domain.observability.extraction_job_probe import ExtractionJobMaterializationObservation
from extraction.domain.prepared_job_package_source import PreparedJobPackageSource
from extraction.infrastructure.extraction_job_workdir_materializer import ExtractionJobWorkdirMaterializer
from extraction.infrastructure.workload_runtime_settings import ExtractionWorkloadRuntimeSettings
from extraction.ports.runtime import ScopedWorkloadCredentials
from tests.unit.extraction.infrastructure.fakes.extraction_job_target_context_enricher import (
    FakeExtractionJobTargetContextEnricher,
)
from shared_kernel.job_package.builder import JobPackageBuilder
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    ContentRef,
    JobPackageId,
    SyncMode,
)


class _RecordingProbe:
    def __init__(self) -> None:
        self.observations: list[ExtractionJobMaterializationObservation] = []

    def repository_files_materialized(self, observation: ExtractionJobMaterializationObservation) -> None:
        self.observations.append(observation)


def _build_package(work_dir: Path, package_id: str, path: str, content: bytes) -> None:
    builder = JobPackageBuilder(
        data_source_id="ds-1",
        knowledge_graph_id="kg-1",
        sync_mode=SyncMode.FULL_REFRESH,
        package_id=JobPackageId(value=package_id),
    )
    ref = builder.add_content(content)
    builder.add_changeset_entry(
        ChangesetEntry(
            operation=ChangeOperation.ADD,
            id="file-1",
            type="io.kartograph.change.file",
            path=path,
            content_ref=ref,
            content_type="text/plain",
            metadata={},
        )
    )
    builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={"commit_sha": "abc"}))
    builder.build(work_dir)


@pytest.mark.asyncio
async def test_prepare_materializes_instance_referenced_paths_and_workspace_layout(tmp_path: Path) -> None:
    package_id = "01JTESTPACK0000000000000002"
    job_packages_dir = tmp_path / "packages"
    job_packages_dir.mkdir()
    extraction_jobs_dir = tmp_path / "extraction_jobs"
    _build_package(
        job_packages_dir,
        package_id,
        "testdata/adapter-configs/cl-stuck/adapter-config.yaml",
        b"adapter: stuck\n",
    )
    package = PreparedJobPackageSource(
        package_id=package_id,
        data_source_id="ds-1",
        data_source_name="hyperfleet-e2e",
        repository_folder="hyperfleet-e2e",
    )
    reader = AsyncMock()
    reader.list_latest_for_knowledge_graph = AsyncMock(return_value=(package,))
    probe = _RecordingProbe()
    materializer = ExtractionJobWorkdirMaterializer(
        settings=ExtractionWorkloadRuntimeSettings(
            extraction_job_work_dir=str(extraction_jobs_dir),
            job_package_work_dir=str(job_packages_dir),
        ),
        prepared_job_package_reader=reader,
        probe=probe,
    )
    job = ExtractionJobRecord(
        id="job-row",
        knowledge_graph_id="kg-1",
        job_id="Adapter Deep Extraction_batch_0001_abcd1234",
        job_set_name="Adapter Deep Extraction",
        strategy="by_instances",
        status=ExtractionJobStatus.PENDING,
        order_index=0,
        description="Extract adapter details.",
        target_instances=(
            ExtractionTargetInstance(
                slug="hyperfleet_e2e_cl_stuck",
                entity_type="Adapter",
                properties={
                    "config_file_path": "testdata/adapter-configs/cl-stuck/adapter-config.yaml",
                },
            ),
        ),
    )

    job_root = await materializer.prepare(
        job=job,
        tenant_id="tenant-1",
        credentials=ScopedWorkloadCredentials(
            token="tok",
            expires_at=datetime.now(UTC),
            scopes=("workload:chat",),
        ),
    )

    repo_file = (
        job_root
        / "repository-files"
        / "hyperfleet-e2e"
        / "testdata/adapter-configs/cl-stuck/adapter-config.yaml"
    )
    assert repo_file.is_file()
    assert (job_root / "mutations").is_dir()
    assert (job_root / "helpers" / "workload-mutations.sh").is_file()
    assert (job_root / "helpers" / "mutation-examples.jsonl").is_file()
    context = json.loads((job_root / "job-context.json").read_text(encoding="utf-8"))
    assert context["repository_files"]["files_written"] == 1
    assert probe.observations[0].files_written == 1


@pytest.mark.asyncio
async def test_prepare_enriches_target_instances_with_graph_id_and_missing_properties(
    tmp_path: Path,
) -> None:
    package_id = "01JTESTPACK0000000000000003"
    job_packages_dir = tmp_path / "packages"
    job_packages_dir.mkdir()
    extraction_jobs_dir = tmp_path / "extraction_jobs"
    _build_package(
        job_packages_dir,
        package_id,
        "testdata/adapter-configs/cl-stuck/adapter-config.yaml",
        b"adapter: stuck\n",
    )
    package = PreparedJobPackageSource(
        package_id=package_id,
        data_source_id="ds-1",
        data_source_name="hyperfleet-e2e",
        repository_folder="hyperfleet-e2e",
    )
    reader = AsyncMock()
    reader.list_latest_for_knowledge_graph = AsyncMock(return_value=(package,))
    materializer = ExtractionJobWorkdirMaterializer(
        settings=ExtractionWorkloadRuntimeSettings(
            extraction_job_work_dir=str(extraction_jobs_dir),
            job_package_work_dir=str(job_packages_dir),
        ),
        prepared_job_package_reader=reader,
        target_context_enricher=FakeExtractionJobTargetContextEnricher(),
    )
    job = ExtractionJobRecord(
        id="job-row",
        knowledge_graph_id="kg-1",
        job_id="Adapter Deep Extraction_batch_0002_abcd1234",
        job_set_name="Adapter Deep Extraction",
        strategy="by_instances",
        status=ExtractionJobStatus.PENDING,
        order_index=0,
        description="Extract adapter details.",
        target_instances=(
            ExtractionTargetInstance(
                slug="hyperfleet_e2e_cl_stuck",
                entity_type="Adapter",
                properties={
                    "config_file_path": "testdata/adapter-configs/cl-stuck/adapter-config.yaml",
                },
            ),
        ),
    )

    job_root = await materializer.prepare(
        job=job,
        tenant_id="tenant-1",
        credentials=ScopedWorkloadCredentials(
            token="tok",
            expires_at=datetime.now(UTC),
            scopes=("workload:chat",),
        ),
    )

    context = json.loads((job_root / "job-context.json").read_text(encoding="utf-8"))
    target = context["target_instances"][0]
    assert target["graph_id"] == "adapter:abc123def4567890"
    assert target["properties_missing"] == ["resource_types", "transport"]
    assert (job_root / "helpers" / "mutation-examples.jsonl").is_file()
