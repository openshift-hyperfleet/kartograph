"""JobPackageReader: reads and validates a JobPackage ZIP archive.

Usage::

    reader = JobPackageReader(archive_path)   # raises if unsafe entry names found
    manifest = reader.read_manifest()
    for entry in reader.iter_changeset():
        data = reader.read_content(entry.content_ref)  # raises on corruption
    checkpoint = reader.read_checkpoint()

All ZIP entry names are validated for path safety on construction.
Content integrity is verified on every :meth:`read_content` call.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections.abc import Iterator
from pathlib import Path

from shared_kernel.job_package.path_safety import validate_zip_entry_name
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangesetEntry,
    ContentRef,
    Manifest,
)


class JobPackageReader:
    """Reads a JobPackage ZIP archive with safety and integrity guarantees.

    On construction, every ZIP entry name is validated against the path-safety
    rules. Any archive containing unsafe entry names (path traversal, absolute
    paths, etc.) raises immediately, preventing malicious archives from causing
    harm later.

    Args:
        archive_path: Path to the JobPackage ZIP file.

    Raises:
        PathSafetyError: If any ZIP entry name violates path safety rules.
        FileNotFoundError: If the archive does not exist.
        zipfile.BadZipFile: If the file is not a valid ZIP archive.
    """

    def __init__(self, archive_path: Path) -> None:
        self._archive_path = archive_path
        self._validate_entry_names()

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def read_manifest(self) -> Manifest:
        """Read and deserialise ``manifest.json`` from the archive.

        Uses ZIP random access — the entire archive is NOT extracted.

        Returns:
            Manifest value object.
        """
        with zipfile.ZipFile(self._archive_path) as zf:
            data = json.loads(zf.read("manifest.json").decode("utf-8"))
        return Manifest.from_dict(data)

    # ------------------------------------------------------------------
    # Changeset
    # ------------------------------------------------------------------

    def iter_changeset(self) -> Iterator[ChangesetEntry]:
        """Iterate over ``changeset.jsonl``, yielding one entry per line.

        Consumers can process entries without loading the entire file into
        memory — the file is read once and lines are yielded lazily.

        Yields:
            ChangesetEntry objects in the order they appear in the file.
        """
        with zipfile.ZipFile(self._archive_path) as zf:
            raw = zf.read("changeset.jsonl").decode("utf-8")

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            yield ChangesetEntry.from_dict(record)

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------

    def read_content(self, content_ref: ContentRef) -> bytes:
        """Read and integrity-verify the raw content for a given ContentRef.

        The consumer strips the ``sha256:`` prefix from ``content_ref`` to
        derive the filename, reads ``content/{hex_digest}`` from the archive,
        then verifies that the SHA-256 of the returned bytes matches the
        filename.

        Args:
            content_ref: The reference to the content file.

        Returns:
            Raw bytes of the content file.

        Raises:
            ValueError: If the stored content does not match the expected hash
                (indicating archive corruption).
            KeyError: If the content file is not present in the archive.
        """
        entry_name = f"content/{content_ref.filename}"
        with zipfile.ZipFile(self._archive_path) as zf:
            raw_bytes = zf.read(entry_name)

        # Integrity verification: recompute SHA-256 and compare to filename
        actual_digest = hashlib.sha256(raw_bytes).hexdigest()
        if actual_digest != content_ref.hex_digest:
            raise ValueError(
                f"Content integrity mismatch for {entry_name!r}: "
                f"expected {content_ref.hex_digest!r}, got {actual_digest!r}. "
                "The archive may be corrupted."
            )

        return raw_bytes

    # ------------------------------------------------------------------
    # Checkpoint
    # ------------------------------------------------------------------

    def read_checkpoint(self) -> AdapterCheckpoint:
        """Read and deserialise ``state.json`` from the archive.

        Returns:
            AdapterCheckpoint value object.
        """
        with zipfile.ZipFile(self._archive_path) as zf:
            data = json.loads(zf.read("state.json").decode("utf-8"))
        return AdapterCheckpoint.from_dict(data)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_entry_names(self) -> None:
        """Validate every ZIP entry name for path safety on construction.

        Raises:
            PathSafetyError: On the first unsafe entry name found.
        """
        with zipfile.ZipFile(self._archive_path) as zf:
            for name in zf.namelist():
                validate_zip_entry_name(name)
