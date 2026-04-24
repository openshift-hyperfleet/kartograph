"""ZIP entry path safety validation.

Prevents path traversal attacks when reading or writing JobPackage ZIP archives.
Both producers (builder) and consumers (reader) use this module to validate
every entry name before writing or after reading.

Spec requirement: ZIP Entry Path Safety
- No leading ``/`` or drive letters
- No ``..`` segments
- Forward-slash separators only
- No null bytes
"""

from __future__ import annotations


class PathSafetyError(ValueError):
    """Raised when a ZIP entry name fails safety validation.

    Subclasses ``ValueError`` so callers that catch ``ValueError`` also
    catch path safety errors without needing to import this exception class.
    """


def validate_zip_entry_name(name: str) -> str:
    """Validate that a ZIP entry name is safe against path traversal.

    Rules (per spec):
    - No leading ``/`` (absolute path).
    - No Windows drive letter (e.g. ``C:``).
    - No backslash separators.
    - No null bytes.
    - No ``..`` path segments anywhere in the name.

    Args:
        name: The ZIP entry name to validate.

    Returns:
        The original ``name`` unchanged if valid (for convenient chaining).

    Raises:
        PathSafetyError: If the entry name violates any safety rule.
    """
    if not name:
        # Empty names are technically harmless but non-sensical.
        return name

    # Rule: no null bytes
    if "\x00" in name:
        raise PathSafetyError(f"ZIP entry name contains a null byte: {name!r}")

    # Rule: no backslash separators
    if "\\" in name:
        raise PathSafetyError(
            f"ZIP entry name uses backslash separators (must be forward-slash only): "
            f"{name!r}"
        )

    # Rule: no leading slash (absolute path)
    if name.startswith("/"):
        raise PathSafetyError(f"ZIP entry name must not have a leading '/': {name!r}")

    # Rule: no Windows drive letter (e.g. "C:" or "c:")
    if len(name) >= 2 and name[1] == ":" and name[0].isalpha():
        raise PathSafetyError(
            f"ZIP entry name must not start with a Windows drive letter: {name!r}"
        )

    # Rule: no ".." segments (path traversal)
    segments = name.split("/")
    if ".." in segments:
        raise PathSafetyError(
            f"ZIP entry name contains a '..' traversal segment: {name!r}"
        )

    return name
