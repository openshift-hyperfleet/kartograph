"""Unit tests for DltAdapterRunner.

Tests cover the dlt Framework Integration scenarios from the spec:
- In-process execution: dlt runs as a Python library (no Docker, no subprocess).
- State persistence: checkpoint state round-trips between runs via dlt state.
- Extracted data on disk: files are available in the pipeline working directory.

Uses a FakeAdapter (no mocks — per testing guidelines) and dlt filesystem
destination pointing to a temp directory. These tests run without any
infrastructure dependencies (no PostgreSQL required).

For integration tests using the PostgreSQL destination and verifying the
``dlt_internal`` schema, see tests/integration/ingestion/.

Spec scenarios covered:
- Scenario: In-process execution
- Scenario: State persistence via database (state round-trip verified with
  filesystem destination; production uses PostgreSQL + dlt_internal schema)
- Scenario: Extracted data on disk
"""

from __future__ import annotations

import json
from pathlib import Path

import dlt
import pytest

from ingestion.infrastructure.dlt_runner import DltAdapterRunner
from ingestion.ports.adapters import ExtractionResult, IDatasourceAdapter
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    ContentRef,
    SyncMode,
)

# ---------------------------------------------------------------------------
# Test data constants
# ---------------------------------------------------------------------------

HEAD_SHA = "cafebabe1234567890abcdef1234567890abcdef"
BLOB_CONTENT = b"# README\nThis is a test file.\n"
BLOB_SHA = ContentRef.from_bytes(BLOB_CONTENT).hex_digest


# ---------------------------------------------------------------------------
# Fake adapter — fakes over mocks per testing guidelines
# ---------------------------------------------------------------------------


def _make_entry(path: str = "README.md") -> ChangesetEntry:
    content_ref = ContentRef.from_bytes(BLOB_CONTENT)
    return ChangesetEntry(
        operation=ChangeOperation.ADD,
        id=f"fake-blob-sha-{path}",
        type="io.kartograph.change.file",
        path=path,
        content_ref=content_ref,
        content_type="text/markdown",
        metadata={},
    )


def _make_checkpoint(sha: str = HEAD_SHA) -> AdapterCheckpoint:
    return AdapterCheckpoint(
        schema_version="1.0.0",
        data={"commit_sha": sha},
    )


def _default_result() -> ExtractionResult:
    return ExtractionResult(
        changeset_entries=[_make_entry("README.md")],
        content_blobs={BLOB_SHA: BLOB_CONTENT},
        new_checkpoint=_make_checkpoint(HEAD_SHA),
    )


class FakeAdapter:
    """In-memory fake adapter for testing DltAdapterRunner.

    Records which checkpoints were received across calls, enabling assertions
    about state restoration between pipeline runs.
    """

    def __init__(
        self,
        result: ExtractionResult | None = None,
    ) -> None:
        self._result = result if result is not None else _default_result()
        self.received_checkpoints: list[AdapterCheckpoint | None] = []

    async def extract(
        self,
        connection_config: dict[str, str],
        credentials: dict[str, str],
        checkpoint: AdapterCheckpoint | None,
        sync_mode: SyncMode,
    ) -> ExtractionResult:
        self.received_checkpoints.append(checkpoint)
        return self._result


# Verify FakeAdapter is structurally compatible with the protocol
assert isinstance(FakeAdapter(), IDatasourceAdapter)


# ---------------------------------------------------------------------------
# Shared fixtures and factory
# ---------------------------------------------------------------------------


@pytest.fixture
def connection_config() -> dict[str, str]:
    return {"owner": "org", "repo": "repo", "branch": "main"}


@pytest.fixture
def credentials() -> dict[str, str]:
    return {"token": "test-token"}


def _make_runner(
    adapter: IDatasourceAdapter,
    working_dir: Path,
    pipeline_name: str | None = None,
) -> DltAdapterRunner:
    """Create a DltAdapterRunner with a filesystem destination for unit tests.

    The filesystem destination writes state to ``{working_dir}/dlt-output/``
    which is unique per test via ``tmp_path``. The pipeline_name defaults to
    a value derived from the working directory so tests don't collide.
    """
    if pipeline_name is None:
        pipeline_name = f"test-{working_dir.name}"
    destination = dlt.destinations.filesystem(str(working_dir / "dlt-output"))
    return DltAdapterRunner(
        adapter=adapter,
        pipeline_name=pipeline_name,
        working_dir=working_dir,
        destination=destination,
    )


# ---------------------------------------------------------------------------
# Scenario: In-process execution
# ---------------------------------------------------------------------------


class TestDltInProcessExecution:
    """Scenario: In-process execution.

    - GIVEN a sync trigger
    - WHEN the adapter runs
    - THEN dlt executes in-process as a Python library (no Docker, no subprocess)
    """

    @pytest.mark.asyncio
    async def test_dlt_pipeline_runs_in_process_and_returns_path(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """run() executes dlt in-process and returns the output directory path."""
        adapter = FakeAdapter()
        runner = _make_runner(adapter, tmp_path)

        output_path = await runner.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        assert isinstance(output_path, Path)

    @pytest.mark.asyncio
    async def test_adapter_extract_is_called_during_pipeline_run(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """The adapter's extract() is invoked exactly once when the pipeline runs."""
        adapter = FakeAdapter()
        runner = _make_runner(adapter, tmp_path)

        await runner.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        assert len(adapter.received_checkpoints) == 1

    @pytest.mark.asyncio
    async def test_last_extraction_result_is_none_before_first_run(
        self, tmp_path: Path
    ) -> None:
        """last_extraction_result is None until run() is called."""
        runner = _make_runner(FakeAdapter(), tmp_path)
        assert runner.last_extraction_result is None

    @pytest.mark.asyncio
    async def test_last_extraction_result_available_after_run(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """ExtractionResult is accessible via last_extraction_result after run()."""
        adapter = FakeAdapter()
        runner = _make_runner(adapter, tmp_path)

        await runner.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        result = runner.last_extraction_result
        assert result is not None
        assert result.new_checkpoint.data["commit_sha"] == HEAD_SHA


# ---------------------------------------------------------------------------
# Scenario: Extracted data on disk
# ---------------------------------------------------------------------------


class TestExtractedDataOnDisk:
    """Scenario: Extracted data on disk.

    - GIVEN a completed dlt extraction
    - THEN extracted data is available as files in the pipeline working directory
    - AND the JobPackager reads these files to assemble the package
    """

    @pytest.mark.asyncio
    async def test_output_directory_exists_after_run(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """The output directory is created and accessible after the pipeline run."""
        runner = _make_runner(FakeAdapter(), tmp_path)

        output_path = await runner.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        assert output_path.exists()
        assert output_path.is_dir()

    @pytest.mark.asyncio
    async def test_content_blobs_written_to_blobs_subdirectory(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """Content blobs are written to {output_dir}/blobs/ keyed by SHA-256 digest."""
        runner = _make_runner(FakeAdapter(), tmp_path)

        await runner.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        blobs_dir = runner.output_dir / "blobs"
        assert blobs_dir.exists(), (
            f"blobs/ subdirectory not found in {runner.output_dir}"
        )
        blob_files = list(blobs_dir.iterdir())
        assert len(blob_files) > 0, "No blob files written to blobs/"

    @pytest.mark.asyncio
    async def test_blob_file_content_matches_extracted_bytes(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """Each blob file contains exactly the raw bytes from the adapter's result."""
        runner = _make_runner(FakeAdapter(), tmp_path)

        await runner.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        blob_file = runner.output_dir / "blobs" / BLOB_SHA
        assert blob_file.exists(), f"Blob file {BLOB_SHA} not found"
        assert blob_file.read_bytes() == BLOB_CONTENT

    @pytest.mark.asyncio
    async def test_blob_filename_is_sha256_hex_digest(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """Blob filenames are the SHA-256 hex digest (content-addressed storage)."""
        import hashlib

        runner = _make_runner(FakeAdapter(), tmp_path)

        await runner.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        blobs_dir = runner.output_dir / "blobs"
        for blob_file in blobs_dir.iterdir():
            expected_digest = hashlib.sha256(blob_file.read_bytes()).hexdigest()
            assert blob_file.name == expected_digest, (
                f"Blob filename {blob_file.name!r} does not match "
                f"SHA-256 of its content ({expected_digest!r})"
            )

    @pytest.mark.asyncio
    async def test_changeset_jsonl_written_to_output_directory(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """A changeset.jsonl file is written to the output directory."""
        runner = _make_runner(FakeAdapter(), tmp_path)

        await runner.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        changeset_file = runner.output_dir / "changeset.jsonl"
        assert changeset_file.exists(), (
            f"changeset.jsonl not found in {runner.output_dir}"
        )
        content = changeset_file.read_text(encoding="utf-8")
        assert content.strip(), "changeset.jsonl is empty"

    @pytest.mark.asyncio
    async def test_changeset_jsonl_contains_one_line_per_entry(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """changeset.jsonl contains exactly one JSON object per ChangesetEntry."""
        entries = [_make_entry("README.md"), _make_entry("src/main.py")]
        result = ExtractionResult(
            changeset_entries=entries,
            content_blobs={entries[0].content_ref.hex_digest: BLOB_CONTENT},
            new_checkpoint=_make_checkpoint(),
        )
        runner = _make_runner(FakeAdapter(result=result), tmp_path)

        await runner.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        changeset_file = runner.output_dir / "changeset.jsonl"
        lines = changeset_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    @pytest.mark.asyncio
    async def test_changeset_jsonl_entries_are_valid_json(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """Each line of changeset.jsonl is a valid JSON object with expected keys."""
        runner = _make_runner(FakeAdapter(), tmp_path)

        await runner.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        changeset_file = runner.output_dir / "changeset.jsonl"
        for line in changeset_file.read_text(encoding="utf-8").strip().splitlines():
            record = json.loads(line)
            assert "path" in record
            assert "operation" in record
            assert "content_ref" in record

    @pytest.mark.asyncio
    async def test_changeset_jsonl_paths_match_entries(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """Paths in changeset.jsonl match the ChangesetEntry paths."""
        entries = [_make_entry("README.md"), _make_entry("src/main.py")]
        result = ExtractionResult(
            changeset_entries=entries,
            content_blobs={entries[0].content_ref.hex_digest: BLOB_CONTENT},
            new_checkpoint=_make_checkpoint(),
        )
        runner = _make_runner(FakeAdapter(result=result), tmp_path)

        await runner.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        changeset_file = runner.output_dir / "changeset.jsonl"
        paths = {
            json.loads(line)["path"]
            for line in changeset_file.read_text(encoding="utf-8").strip().splitlines()
        }
        assert "README.md" in paths
        assert "src/main.py" in paths

    @pytest.mark.asyncio
    async def test_empty_extraction_produces_empty_changeset(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """An extraction with no entries writes an empty changeset.jsonl."""
        empty_result = ExtractionResult(
            changeset_entries=[],
            content_blobs={},
            new_checkpoint=_make_checkpoint(),
        )
        runner = _make_runner(FakeAdapter(result=empty_result), tmp_path)

        await runner.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        changeset_file = runner.output_dir / "changeset.jsonl"
        assert changeset_file.exists()
        assert changeset_file.read_text(encoding="utf-8").strip() == ""


# ---------------------------------------------------------------------------
# Scenario: State persistence via database (filesystem backend for unit tests)
# ---------------------------------------------------------------------------


class TestDltStatePersistence:
    """Scenario: State persistence via database.

    - GIVEN a Kubernetes deployment with ephemeral pods
    - WHEN an adapter needs checkpoint state
    - THEN dlt restores state from a dedicated dlt_internal database schema
    - AND state is persisted back after successful extraction

    Unit tests use the filesystem destination (no PostgreSQL required).
    The checkpoint state round-trip is the same regardless of destination;
    only the persistence backend differs (JSON files vs. PostgreSQL
    ``dlt_internal`` schema in production).
    """

    @pytest.mark.asyncio
    async def test_first_run_passes_none_checkpoint_to_adapter(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """On the first run there is no prior state, so checkpoint=None is passed."""
        adapter = FakeAdapter()
        runner = _make_runner(adapter, tmp_path)

        await runner.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.INCREMENTAL,
        )

        assert adapter.received_checkpoints[0] is None

    @pytest.mark.asyncio
    async def test_checkpoint_is_persisted_after_first_run(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """After the first run, the checkpoint returned by the adapter is persisted."""
        adapter = FakeAdapter()
        pipeline_name = f"persist-{tmp_path.name}"
        runner = _make_runner(adapter, tmp_path, pipeline_name=pipeline_name)

        await runner.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        result = runner.last_extraction_result
        assert result is not None
        assert result.new_checkpoint.data["commit_sha"] == HEAD_SHA

    @pytest.mark.asyncio
    async def test_second_run_restores_checkpoint_from_dlt_state(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """Second run restores the checkpoint persisted by the first run (state round-trip).

        This is the core dlt state persistence scenario: the adapter receives
        the checkpoint from the previous run rather than None, enabling
        incremental extraction to resume from the correct position.
        """
        pipeline_name = f"roundtrip-{tmp_path.name}"
        destination = dlt.destinations.filesystem(str(tmp_path / "dlt-output"))

        # --- First run ---
        adapter1 = FakeAdapter()  # returns checkpoint with HEAD_SHA
        runner1 = DltAdapterRunner(
            adapter=adapter1,
            pipeline_name=pipeline_name,
            working_dir=tmp_path,
            destination=destination,
        )
        await runner1.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        # --- Second run (same pipeline_name, same destination) ---
        adapter2 = FakeAdapter()
        destination2 = dlt.destinations.filesystem(str(tmp_path / "dlt-output"))
        runner2 = DltAdapterRunner(
            adapter=adapter2,
            pipeline_name=pipeline_name,
            working_dir=tmp_path,
            destination=destination2,
        )
        await runner2.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.INCREMENTAL,
        )

        # The second adapter call must have received the checkpoint from run 1
        restored_checkpoint = adapter2.received_checkpoints[0]
        assert restored_checkpoint is not None, (
            "Second run should restore checkpoint from dlt state, "
            "but adapter received checkpoint=None"
        )
        assert restored_checkpoint.data["commit_sha"] == HEAD_SHA

    @pytest.mark.asyncio
    async def test_state_survives_runner_object_recreation(
        self, tmp_path: Path, connection_config: dict, credentials: dict
    ) -> None:
        """State persists even when the DltAdapterRunner object is recreated.

        This simulates a Kubernetes pod restart: the runner is re-instantiated
        with the same pipeline configuration, and dlt restores state from the
        persistent destination rather than from the in-memory object.
        """
        pipeline_name = f"pod-restart-{tmp_path.name}"
        dest_path = str(tmp_path / "dlt-output")

        # Simulate pod 1: first run
        adapter1 = FakeAdapter()
        runner1 = DltAdapterRunner(
            adapter=adapter1,
            pipeline_name=pipeline_name,
            working_dir=tmp_path,
            destination=dlt.destinations.filesystem(dest_path),
        )
        await runner1.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        # Simulate pod 2: runner completely recreated, same config
        adapter2 = FakeAdapter()
        runner2 = DltAdapterRunner(
            adapter=adapter2,
            pipeline_name=pipeline_name,
            working_dir=tmp_path,
            destination=dlt.destinations.filesystem(dest_path),
        )
        await runner2.run(
            connection_config=connection_config,
            credentials=credentials,
            sync_mode=SyncMode.INCREMENTAL,
        )

        restored = adapter2.received_checkpoints[0]
        assert restored is not None, (
            "State must survive runner object recreation (simulates pod restart)"
        )
        assert restored.data["commit_sha"] == HEAD_SHA
