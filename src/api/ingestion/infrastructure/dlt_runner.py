"""dlt-based adapter pipeline runner for the Ingestion bounded context.

Wraps any IDatasourceAdapter in a dlt pipeline that:

1. **Runs in-process** as a Python library (no Docker, no subprocess).
2. **Persists checkpoint state** via dlt's built-in state mechanism.  When the
   destination is PostgreSQL, state lands in the ``dlt_internal`` database
   schema — surviving Kubernetes pod restarts. When the destination is
   ``filesystem``, state is stored as JSON files (useful for development and
   unit tests).
3. **Writes extracted data to disk** in the pipeline working directory so the
   downstream JobPackager can assemble the ZIP archive without going through the
   destination database.

Architecture note: this is the only module in the Ingestion context that imports
dlt. The ``IDatasourceAdapter`` port and all domain types remain dlt-free.
"""

from __future__ import annotations

import asyncio
import functools
import json
from pathlib import Path
from typing import Any

import dlt

from ingestion.ports.adapters import ExtractionResult, IDatasourceAdapter
from shared_kernel.job_package.value_objects import AdapterCheckpoint, SyncMode

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# dlt source / resource names used as state-dict keys in the destination.
_SOURCE_NAME = "kartograph_adapter"
_RESOURCE_NAME = "changeset_entries"

# Key within the dlt resource state dict where we persist the adapter checkpoint.
_CHECKPOINT_STATE_KEY = "adapter_checkpoint"

# Subdirectory within output_dir for raw content blobs (content-addressed).
_BLOBS_SUBDIR = "blobs"

# Name of the JSONL file written to output_dir.
_CHANGESET_FILENAME = "changeset.jsonl"


# ---------------------------------------------------------------------------
# DltAdapterRunner
# ---------------------------------------------------------------------------


class DltAdapterRunner:
    """In-process dlt pipeline runner for any IDatasourceAdapter.

    Manages checkpoint state via dlt's resource state mechanism so that
    incremental syncs resume from the correct position across pod restarts.
    The state is persisted to the configured destination on every successful
    run.

    Writes two kinds of output to ``working_dir / "output"`` for the
    JobPackager:

    * ``changeset.jsonl`` — one JSON line per ChangesetEntry.
    * ``blobs/{hex_digest}`` — raw bytes for every content blob, named by
      their SHA-256 hex digest (content-addressed storage).

    Args:
        adapter: The data source adapter implementing IDatasourceAdapter.
        pipeline_name: Unique pipeline identifier (e.g. ``"kartograph-{id}"``).
            Used as the key under which dlt stores state in the destination.
            For PostgreSQL this maps to ``dlt_internal`` schema tables; for
            the filesystem destination it maps to JSON state files.
        working_dir: Base directory.  Sub-directories created automatically:
            ``{working_dir}/pipelines/`` — dlt internal state cache.
            ``{working_dir}/output/`` — files for the JobPackager.
        destination: dlt destination instance.  Use
            ``dlt.destinations.postgres(...)`` in production (state in
            ``dlt_internal`` schema) and ``dlt.destinations.filesystem(...)``
            for development / unit tests.
    """

    def __init__(
        self,
        adapter: IDatasourceAdapter,
        pipeline_name: str,
        working_dir: Path,
        destination: Any,
    ) -> None:
        self._adapter = adapter
        self._pipeline_name = pipeline_name
        self._working_dir = working_dir
        self._destination = destination
        self._last_result: ExtractionResult | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def last_extraction_result(self) -> ExtractionResult | None:
        """The ExtractionResult from the most recent run, or ``None``."""
        return self._last_result

    @property
    def output_dir(self) -> Path:
        """Directory where extracted files are written for the JobPackager."""
        return self._working_dir / "output"

    async def run(
        self,
        connection_config: dict[str, str],
        credentials: dict[str, str],
        sync_mode: SyncMode,
    ) -> Path:
        """Run the adapter via a dlt pipeline.

        Executes the pipeline in a thread-pool executor so that:
        - The caller's asyncio event loop is not blocked.
        - The adapter's async ``extract()`` can be driven by a fresh event loop
          created inside the worker thread (avoids conflicts with the caller's
          event loop).

        State (checkpoint) is persisted to the destination by dlt at the end of
        each successful run and restored automatically at the start of the next.

        Returns:
            Path to the output directory containing:
            ``changeset.jsonl`` and ``blobs/{hex_digest}`` files.
        """
        loop = asyncio.get_running_loop()
        extraction_result, output_path = await loop.run_in_executor(
            None,
            functools.partial(
                self._run_pipeline_in_thread,
                connection_config=connection_config,
                credentials=credentials,
                sync_mode=sync_mode,
            ),
        )
        self._last_result = extraction_result
        return output_path

    # ------------------------------------------------------------------
    # Private implementation
    # ------------------------------------------------------------------

    def _run_pipeline_in_thread(
        self,
        connection_config: dict[str, str],
        credentials: dict[str, str],
        sync_mode: SyncMode,
    ) -> tuple[ExtractionResult, Path]:
        """Execute the dlt pipeline synchronously inside a worker thread.

        Creates a dedicated asyncio event loop for this thread so the async
        adapter can be driven without interfering with the caller's event loop.

        Returns:
            Tuple of (ExtractionResult, output directory Path).
        """
        # Prepare directories
        pipelines_dir = self._working_dir / "pipelines"
        pipelines_dir.mkdir(parents=True, exist_ok=True)
        output_dir = self._working_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create a fresh event loop for this thread.
        # asyncio.new_event_loop() is safe inside a ThreadPoolExecutor thread.
        inner_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(inner_loop)

        # Holder populated by the dlt resource so the caller can retrieve it.
        result_holder: list[ExtractionResult] = []

        adapter = self._adapter

        try:
            # Define the dlt source and resource inside the thread so they
            # capture the correct local variables via closure.
            @dlt.source(name=_SOURCE_NAME)
            def _adapter_source() -> Any:  # noqa: ANN202
                @dlt.resource(name=_RESOURCE_NAME)
                def _changeset_entries() -> Any:  # noqa: ANN202
                    # --------------------------------------------------
                    # 1. Restore checkpoint from dlt resource state
                    # --------------------------------------------------
                    state = dlt.current.resource_state()
                    checkpoint_data: dict[str, Any] | None = state.get(
                        _CHECKPOINT_STATE_KEY
                    )
                    checkpoint: AdapterCheckpoint | None = None
                    if checkpoint_data is not None:
                        checkpoint = AdapterCheckpoint.from_dict(checkpoint_data)

                    # --------------------------------------------------
                    # 2. Run the async adapter in this thread's event loop
                    # --------------------------------------------------
                    extraction_result = inner_loop.run_until_complete(
                        adapter.extract(
                            connection_config=connection_config,
                            credentials=credentials,
                            checkpoint=checkpoint,
                            sync_mode=sync_mode,
                        )
                    )

                    # --------------------------------------------------
                    # 3. Persist new checkpoint back to dlt state
                    #    (dlt writes this to the destination on run completion)
                    # --------------------------------------------------
                    state[_CHECKPOINT_STATE_KEY] = (
                        extraction_result.new_checkpoint.to_dict()
                    )

                    # --------------------------------------------------
                    # 4. Write output files for the JobPackager
                    # --------------------------------------------------
                    _write_output_files(output_dir, extraction_result)

                    # Expose result to the outer function
                    result_holder.append(extraction_result)

                    # --------------------------------------------------
                    # 5. Yield changeset entries as dlt records
                    #    (dlt loads these to the destination)
                    # --------------------------------------------------
                    for entry in extraction_result.changeset_entries:
                        yield entry.to_dict()

                return _changeset_entries()

            # Build and run the pipeline.
            pipeline = dlt.pipeline(
                pipeline_name=self._pipeline_name,
                destination=self._destination,
                dataset_name="kartograph_extraction",
                pipelines_dir=str(pipelines_dir),
            )
            pipeline.run(_adapter_source())

        finally:
            inner_loop.close()
            asyncio.set_event_loop(None)

        # If the adapter produced no entries, result_holder is still populated
        # because _write_output_files was called.  Guard against the edge case
        # where the resource function raised before appending.
        if result_holder:
            extraction_result = result_holder[0]
        else:
            extraction_result = ExtractionResult(
                changeset_entries=[],
                content_blobs={},
                new_checkpoint=AdapterCheckpoint(schema_version="1.0.0", data={}),
            )

        return extraction_result, output_dir


# ---------------------------------------------------------------------------
# File I/O helpers (module-level so they can be tested independently)
# ---------------------------------------------------------------------------


def _write_output_files(output_dir: Path, result: ExtractionResult) -> None:
    """Write changeset.jsonl and content blobs to the output directory.

    Called by the dlt resource during pipeline execution so the files are
    available as soon as the pipeline run completes, regardless of whether
    the destination load has finished.

    Args:
        output_dir: Target directory (must already exist).
        result: The extraction result to serialise.
    """
    # Write content blobs as individual files named by SHA-256 hex digest.
    if result.content_blobs:
        blobs_dir = output_dir / _BLOBS_SUBDIR
        blobs_dir.mkdir(exist_ok=True)
        for hex_digest, raw_bytes in result.content_blobs.items():
            (blobs_dir / hex_digest).write_bytes(raw_bytes)

    # Write changeset.jsonl (one JSON object per line).
    changeset_path = output_dir / _CHANGESET_FILENAME
    with changeset_path.open("w", encoding="utf-8") as fh:
        for entry in result.changeset_entries:
            fh.write(json.dumps(entry.to_dict()) + "\n")
