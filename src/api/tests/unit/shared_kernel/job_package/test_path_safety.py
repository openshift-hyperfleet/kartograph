"""Unit tests for ZIP entry path safety validation (TDD - tests first).

Spec: specs/shared-kernel/job-package.spec.md
Requirement: ZIP Entry Path Safety
"""

from __future__ import annotations

import pytest

from shared_kernel.job_package.path_safety import (
    PathSafetyError,
    validate_zip_entry_name,
)


class TestValidateZipEntryName:
    """Tests for validate_zip_entry_name function.

    Scenario: ZIP entry path safety
    - GIVEN any ZIP entry in the archive
    - THEN its name MUST be a normalized relative path:
      - no leading `/` or drive letters
      - no `..` segments
      - forward-slash separators only
    """

    def test_accepts_simple_file(self):
        """A simple filename is valid."""
        validate_zip_entry_name("manifest.json")

    def test_accepts_file_in_directory(self):
        """A file inside a directory using forward slash is valid."""
        validate_zip_entry_name("content/a3f2c1d")

    def test_accepts_content_directory_entry(self):
        """The content/ directory entry is valid."""
        validate_zip_entry_name("content/")

    def test_accepts_changeset_jsonl(self):
        """changeset.jsonl is valid."""
        validate_zip_entry_name("changeset.jsonl")

    def test_accepts_state_json(self):
        """state.json is valid."""
        validate_zip_entry_name("state.json")

    def test_rejects_leading_slash(self):
        """Entry names must not start with /."""
        with pytest.raises(PathSafetyError, match="leading"):
            validate_zip_entry_name("/etc/passwd")

    def test_rejects_double_dot_segment(self):
        """Entry names must not contain .. path traversal."""
        with pytest.raises(PathSafetyError, match=r"\.\.|traversal"):
            validate_zip_entry_name("content/../../../etc/passwd")

    def test_rejects_double_dot_at_start(self):
        """Entry names must not start with .. segment."""
        with pytest.raises(PathSafetyError, match=r"\.\.|traversal"):
            validate_zip_entry_name("../secret")

    def test_rejects_windows_drive_letter(self):
        """Entry names must not start with a Windows drive letter (C:/)."""
        with pytest.raises(PathSafetyError, match="drive"):
            validate_zip_entry_name("C:/Windows/system32")

    def test_rejects_backslash_separator(self):
        """Entry names must use forward-slash separators only."""
        with pytest.raises(PathSafetyError, match="backslash|separator"):
            validate_zip_entry_name("content\\somefile")

    def test_rejects_null_byte(self):
        """Entry names must not contain null bytes."""
        with pytest.raises(PathSafetyError):
            validate_zip_entry_name("content/\x00malicious")

    def test_rejects_double_dot_middle_segment(self):
        """Traversal segments embedded in the path are rejected."""
        with pytest.raises(PathSafetyError, match=r"\.\.|traversal"):
            validate_zip_entry_name("content/subdir/../../../etc/hosts")

    def test_rejects_lowercase_drive_letter(self):
        """Lowercase Windows drive letters also rejected."""
        with pytest.raises(PathSafetyError, match="drive"):
            validate_zip_entry_name("c:/Users/victim/file.txt")

    def test_accepts_hex_content_filename(self):
        """A hex-digest filename in content/ is valid."""
        hex_name = "a" * 64
        validate_zip_entry_name(f"content/{hex_name}")

    def test_accepts_nested_content_path(self):
        """Nested paths without traversal are valid."""
        validate_zip_entry_name("content/subdir/file.dat")


class TestValidateZipEntryNameReturnValue:
    """validate_zip_entry_name returns the name on success for chaining."""

    def test_returns_name_on_success(self):
        """On success, returns the validated name."""
        name = "manifest.json"
        result = validate_zip_entry_name(name)
        assert result == name
