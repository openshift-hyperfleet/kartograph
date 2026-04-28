"""Unit tests for IngestionService.

Tests the orchestration of: adapter extract → package build → JobPackageId returned.
Uses fakes for adapter, outbox, and work directory.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ingestion.application.services.ingestion_service import IngestionService
from ingestion.ports.adapters import ExtractionResult, IDatasourceAdapter
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    ContentRef,
    JobPackageId,
    SyncMode,
)


def _make_extraction_result(
    item_id: str = "file-001",
    path: str = "src/main.py",
    content: bytes = b"print('hello')",
) -> ExtractionResult:
    """Build a minimal ExtractionResult with one changeset entry."""
    content_ref = ContentRef.from_bytes(content)
    entry = ChangesetEntry(
        operation=ChangeOperation.ADD,
        id=item_id,
        type="io.kartograph.change.file",
        path=path,
        content_ref=content_ref,
        content_type="text/x-python",
        metadata={},
    )
    checkpoint = AdapterCheckpoint(schema_version="1.0.0", data={})
    return ExtractionResult(
        changeset_entries=[entry],
        content_blobs={content_ref.hex_digest: content},
        new_checkpoint=checkpoint,
    )


class _FakeAdapter:
    """Fake adapter that returns an ExtractionResult or raises."""

    def __init__(
        self,
        result: ExtractionResult | None = None,
        fail: bool = False,
    ) -> None:
        self._result = result
        self._fail = fail

    async def extract(
        self,
        connection_config: dict[str, str],
        credentials: dict[str, str],
        checkpoint: AdapterCheckpoint | None,
        sync_mode: SyncMode,
    ) -> ExtractionResult:
        if self._fail:
            raise RuntimeError("credentials expired")
        if self._result is not None:
            return self._result
        # Empty result
        return ExtractionResult(
            changeset_entries=[],
            content_blobs={},
            new_checkpoint=AdapterCheckpoint(schema_version="1.0.0", data={}),
        )


@pytest.mark.asyncio
class TestIngestionService:
    """Tests for IngestionService.run()."""

    async def test_run_returns_job_package_id(self):
        """run() should return a JobPackageId when adapter succeeds."""
        result = _make_extraction_result()
        adapter = _FakeAdapter(result=result)
        registry: dict[str, IDatasourceAdapter] = {"github": adapter}
        with tempfile.TemporaryDirectory() as tmpdir:
            service = IngestionService(
                adapter_registry=registry,
                work_dir=Path(tmpdir),
            )
            job_id = await service.run(
                sync_run_id="run-001",
                data_source_id="ds-001",
                knowledge_graph_id="kg-001",
                adapter_type="github",
                connection_config={"repo": "org/repo"},
                credentials_path=None,
            )

        assert isinstance(job_id, JobPackageId)

    async def test_run_creates_zip_archive(self):
        """run() should create a ZIP archive in the work directory."""
        result = _make_extraction_result()
        adapter = _FakeAdapter(result=result)
        registry: dict[str, IDatasourceAdapter] = {"github": adapter}
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            service = IngestionService(
                adapter_registry=registry,
                work_dir=work_dir,
            )
            job_id = await service.run(
                sync_run_id="run-001",
                data_source_id="ds-001",
                knowledge_graph_id="kg-001",
                adapter_type="github",
                connection_config={"repo": "org/repo"},
                credentials_path=None,
            )
            # The archive should exist
            archive_path = work_dir / job_id.archive_name()
            assert archive_path.exists()

    async def test_run_raises_for_unknown_adapter(self):
        """run() should raise ValueError when adapter type is unknown."""
        service = IngestionService(
            adapter_registry={},
            work_dir=Path("/tmp"),
        )
        with pytest.raises(ValueError, match="Unknown adapter"):
            await service.run(
                sync_run_id="run-001",
                data_source_id="ds-001",
                knowledge_graph_id="kg-001",
                adapter_type="unknown_adapter",
                connection_config={},
                credentials_path=None,
            )

    async def test_run_propagates_adapter_errors(self):
        """run() should propagate exceptions from adapters."""
        adapter = _FakeAdapter(fail=True)
        registry: dict[str, IDatasourceAdapter] = {"github": adapter}
        with tempfile.TemporaryDirectory() as tmpdir:
            service = IngestionService(
                adapter_registry=registry,
                work_dir=Path(tmpdir),
            )
            with pytest.raises(RuntimeError, match="credentials expired"):
                await service.run(
                    sync_run_id="run-001",
                    data_source_id="ds-001",
                    knowledge_graph_id="kg-001",
                    adapter_type="github",
                    connection_config={},
                    credentials_path=None,
                )

    async def test_run_handles_empty_changeset(self):
        """run() should succeed with empty changeset (no-op sync)."""
        adapter = _FakeAdapter()  # returns empty ExtractionResult
        registry: dict[str, IDatasourceAdapter] = {"github": adapter}
        with tempfile.TemporaryDirectory() as tmpdir:
            service = IngestionService(
                adapter_registry=registry,
                work_dir=Path(tmpdir),
            )
            job_id = await service.run(
                sync_run_id="run-001",
                data_source_id="ds-001",
                knowledge_graph_id="kg-001",
                adapter_type="github",
                connection_config={},
                credentials_path=None,
            )
        assert isinstance(job_id, JobPackageId)
