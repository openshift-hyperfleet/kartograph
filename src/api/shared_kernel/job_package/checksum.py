"""Content directory checksum computation.

Computes a deterministic SHA-256 checksum of the ``content/`` directory
in a JobPackage. The checksum is OS-independent, filesystem-order-independent,
and excludes file metadata (timestamps, permissions).

Algorithm (per spec):
1. Walk the directory recursively.
2. For symlinks: resolve to target; skip if outside ``content/`` root or
   if the target has already been visited (cycle detection).
3. Include only regular files whose name matches ``[0-9a-f]+``.
4. Normalize each path to POSIX format with no leading ``./``.
5. Sort entries lexicographically by normalized path.
6. For each file in sorted order, append to a byte stream:
   - normalized path (UTF-8)
   - newline (``\\n``)
   - raw file bytes
7. Return the hex-encoded SHA-256 of the accumulated stream.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

# Regex for valid content filenames: lowercase hex characters only
_HEX_PATTERN = re.compile(r"^[0-9a-f]+$")


def compute_content_checksum(content_dir: Path) -> str:
    """Compute a deterministic SHA-256 checksum of the content directory.

    The checksum covers only content files — i.e., files whose name is
    composed entirely of lowercase hexadecimal characters. All other files
    (e.g. ``README.txt``, ``.DS_Store``) are excluded.

    Symlinks within the content directory root are followed; symlinks that
    resolve to paths outside the root, or that create cycles, are skipped.

    Args:
        content_dir: Path to the ``content/`` directory.

    Returns:
        Lowercase hex-encoded SHA-256 digest string (64 characters).
    """
    hasher = hashlib.sha256()
    content_root = content_dir.resolve()

    # Collect (normalized_path, resolved_file_path) pairs
    entries: list[tuple[str, Path]] = []
    visited_real_paths: set[Path] = set()

    for candidate in content_dir.rglob("*"):
        # Resolve symlinks
        if candidate.is_symlink():
            try:
                resolved = candidate.resolve()
            except OSError:
                continue  # broken symlink — skip

            # Skip if target is outside content root (out-of-tree symlink)
            try:
                resolved.relative_to(content_root)
            except ValueError:
                continue  # out-of-tree — skip

            # Cycle detection via resolved paths
            if resolved in visited_real_paths:
                continue

            if not resolved.is_file():
                continue

            actual_path = resolved
        else:
            if not candidate.is_file():
                continue
            actual_path = candidate

        # Only include files whose name matches [0-9a-f]+
        if not _HEX_PATTERN.match(candidate.name):
            continue

        # Normalize path relative to content_dir, using POSIX separators
        try:
            rel_path = candidate.relative_to(content_dir)
        except ValueError:
            continue
        normalized = rel_path.as_posix()

        visited_real_paths.add(actual_path)
        entries.append((normalized, actual_path))

    # Sort lexicographically by normalized path
    entries.sort(key=lambda pair: pair[0])

    # Build canonical byte stream
    for normalized, actual_path in entries:
        hasher.update(normalized.encode("utf-8"))
        hasher.update(b"\n")
        hasher.update(actual_path.read_bytes())

    return hasher.hexdigest()
