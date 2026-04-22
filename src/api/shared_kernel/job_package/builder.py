"""JobPackageBuilder: assembles a JobPackage ZIP archive.

Usage::

    builder = JobPackageBuilder(
        data_source_id="ds-01",
        knowledge_graph_id="kg-01",
        sync_mode=SyncMode.INCREMENTAL,
    )
    ref = builder.add_content(raw_bytes)
    builder.add_changeset_entry(ChangesetEntry(operation=ChangeOperation.ADD, ...))
    builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
    archive_path = builder.build(output_dir)

The builder validates all ZIP entry names before writing to prevent path
traversal vulnerabilities.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from shared_kernel.job_package.path_safety import validate_zip_entry_name
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangesetEntry,
    ContentRef,
    JobPackageId,
    Manifest,
    SyncMode,
)

# Package format version — bump the minor or patch when the format changes,
# major when backwards-incompatible changes are made.
_FORMAT_VERSION = "1.0.0"


class JobPackageBuilder:
    """Assembles a JobPackage ZIP archive from ingestion artefacts.

    The builder accumulates content, changeset entries, and the adapter
    checkpoint in memory, then writes everything to a single ZIP file when
    ``build()`` is called.

    Content is automatically deduplicated: adding the same raw bytes twice
    stores only one file in the ``content/`` directory.

    Args:
        data_source_id: ID of the DataSource that produced this package.
        knowledge_graph_id: ID of the KnowledgeGraph this package feeds.
        sync_mode: Whether this run is incremental or a full refresh.
        package_id: Optional pre-existing ULID for the package.  If omitted,
            a new ULID is generated.
    """

    def __init__(
        self,
        data_source_id: str,
        knowledge_graph_id: str,
        sync_mode: SyncMode,
        package_id: JobPackageId | None = None,
    ) -> None:
        self._data_source_id = data_source_id
        self._knowledge_graph_id = knowledge_graph_id
        self._sync_mode = sync_mode
        self._package_id: JobPackageId = package_id or JobPackageId.generate()

        # Content store: hex_digest -> raw bytes (deduplicated)
        self._content: dict[str, bytes] = {}

        # Changeset entries in insertion order
        self._changeset_entries: list[ChangesetEntry] = []

        # Adapter checkpoint (required before build)
        self._checkpoint: AdapterCheckpoint | None = None

    # ------------------------------------------------------------------
    # Builder methods
    # ------------------------------------------------------------------

    def add_content(self, raw_bytes: bytes) -> ContentRef:
        """Store raw content and return its ContentRef.

        If the same bytes have already been added, the existing ContentRef
        is returned without duplicating the storage.

        Args:
            raw_bytes: Raw content bytes to store.

        Returns:
            ContentRef pointing to this content in the ``content/`` directory.
        """
        ref = ContentRef.from_bytes(raw_bytes)
        self._content[ref.hex_digest] = raw_bytes
        return ref

    def add_changeset_entry(self, entry: ChangesetEntry) -> None:
        """Append a changeset entry.

        Args:
            entry: The changeset entry to include in ``changeset.jsonl``.
        """
        self._changeset_entries.append(entry)

    def set_checkpoint(self, checkpoint: AdapterCheckpoint) -> None:
        """Set the adapter checkpoint snapshot for ``state.json``.

        Args:
            checkpoint: The adapter checkpoint to embed.
        """
        self._checkpoint = checkpoint

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, output_dir: Path) -> Path:
        """Assemble the JobPackage ZIP archive and write it to *output_dir*.

        Args:
            output_dir: Directory in which to create the archive.

        Returns:
            Absolute path to the newly written ZIP file.

        Raises:
            ValueError: If no checkpoint has been set before calling build().
        """
        if self._checkpoint is None:
            raise ValueError(
                "A checkpoint must be set via set_checkpoint() before build()."
            )

        archive_path = output_dir / self._package_id.archive_name()

        # Compute content checksum from in-memory store
        content_checksum = self._compute_content_checksum()

        manifest = Manifest(
            format_version=_FORMAT_VERSION,
            data_source_id=self._data_source_id,
            knowledge_graph_id=self._knowledge_graph_id,
            sync_mode=self._sync_mode,
            entry_count=len(self._changeset_entries),
            content_checksum=content_checksum,
        )

        with zipfile.ZipFile(
            archive_path, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as zf:
            # 1. manifest.json
            self._write_json(zf, "manifest.json", manifest.to_dict())

            # 2. changeset.jsonl
            self._write_changeset(zf)

            # 3. content/ files
            self._write_content(zf)

            # 4. state.json
            self._write_json(zf, "state.json", self._checkpoint.to_dict())

        return archive_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_content_checksum(self) -> str:
        """Compute the canonical content checksum from the in-memory store.

        The algorithm mirrors what :func:`compute_content_checksum` does on
        a filesystem directory:
        - Sort hex digests lexicographically (they are the filenames).
        - For each hex digest, append ``{digest}\\n{raw_bytes}`` to the stream.
        - Return the hex-encoded SHA-256.
        """
        hasher = hashlib.sha256()
        for hex_digest in sorted(self._content.keys()):
            hasher.update(hex_digest.encode("utf-8"))
            hasher.update(b"\n")
            hasher.update(self._content[hex_digest])
        return hasher.hexdigest()

    def _write_json(self, zf: zipfile.ZipFile, entry_name: str, data: dict) -> None:
        """Write a JSON object as a ZIP entry."""
        validate_zip_entry_name(entry_name)
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        zf.writestr(entry_name, payload)

    def _write_changeset(self, zf: zipfile.ZipFile) -> None:
        """Write all changeset entries as JSONL to ``changeset.jsonl``."""
        validate_zip_entry_name("changeset.jsonl")
        lines = []
        for entry in self._changeset_entries:
            line = json.dumps(
                entry.to_dict(), ensure_ascii=False, separators=(",", ":")
            )
            lines.append(line)
        payload = "\n".join(lines)
        if payload:
            payload += "\n"
        zf.writestr("changeset.jsonl", payload.encode("utf-8"))

    def _write_content(self, zf: zipfile.ZipFile) -> None:
        """Write all content files under ``content/`` in the ZIP."""
        for hex_digest, raw_bytes in sorted(self._content.items()):
            entry_name = f"content/{hex_digest}"
            validate_zip_entry_name(entry_name)
            zf.writestr(entry_name, raw_bytes)
