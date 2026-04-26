"""Unit tests for IngestionService.

Tests the orchestration of: adapter extract → package build → JobPackageId returned.
Uses fakes for adapter, outbox, and work directory.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ingestion.application.services.ingestion_service import IngestionService
from ingestion.ports.adapters import RawItem
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    JobPackageId,
)


class _FakeAdapter:
    """Fake adapter that returns a single raw item."""

    def __init__(self, items: list[RawItem], fail: bool = False) -> None:
        self._items = items
        self._fail = fail

    async def extract(
        self,
        connection_config: dict[str, str],
        credentials: dict[str, str] | None = None,
    ) -> tuple[list[RawItem], AdapterCheckpoint]:
        if self._fail:
            raise RuntimeError("credentials expired")
        checkpoint = AdapterCheckpoint(schema_version="1.0.0", data={})
        return self._items, checkpoint


def _make_raw_item(
    item_id: str = "file-001",
    path: str = "src/main.py",
    content: bytes = b"print('hello')",
) -> RawItem:
    return RawItem(
        operation=ChangeOperation.ADD,
        id=item_id,
        type="io.kartograph.change.file",
        path=path,
        content_bytes=content,
        content_type="text/x-python",
        metadata={},
    )


@pytest.mark.asyncio
class TestIngestionService:
    """Tests for IngestionService.run()."""

    async def test_run_returns_job_package_id(self):
        """run() should return a JobPackageId when adapter succeeds."""
        item = _make_raw_item()
        adapter = _FakeAdapter(items=[item])
        registry = {"github": adapter}

        with tempfile.TemporaryDirectory() as tmpdir:
            service = IngestionService(
                adapter_registry=registry,
                work_dir=Path(tmpdir),
            )
            result = await service.run(
                sync_run_id="run-001",
                data_source_id="ds-001",
                knowledge_graph_id="kg-001",
                adapter_type="github",
                connection_config={"repo": "org/repo"},
                credentials_path=None,
            )

        assert isinstance(result, JobPackageId)

    async def test_run_creates_zip_archive(self):
        """run() should create a ZIP archive in the work directory."""
        item = _make_raw_item()
        adapter = _FakeAdapter(items=[item])
        registry = {"github": adapter}

        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            service = IngestionService(
                adapter_registry=registry,
                work_dir=work_dir,
            )
            result = await service.run(
                sync_run_id="run-001",
                data_source_id="ds-001",
                knowledge_graph_id="kg-001",
                adapter_type="github",
                connection_config={"repo": "org/repo"},
                credentials_path=None,
            )
            # The archive should exist
            archive_path = work_dir / result.archive_name()
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
        adapter = _FakeAdapter(items=[], fail=True)
        registry = {"github": adapter}

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
        adapter = _FakeAdapter(items=[])
        registry = {"github": adapter}

        with tempfile.TemporaryDirectory() as tmpdir:
            service = IngestionService(
                adapter_registry=registry,
                work_dir=Path(tmpdir),
            )
            result = await service.run(
                sync_run_id="run-001",
                data_source_id="ds-001",
                knowledge_graph_id="kg-001",
                adapter_type="github",
                connection_config={},
                credentials_path=None,
            )
        assert isinstance(result, JobPackageId)
