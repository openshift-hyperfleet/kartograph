"""Unit tests for content checksum computation (TDD - tests first).

Spec: specs/shared-kernel/job-package.spec.md
Requirement: Manifest / Content Checksum Computation
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path


from shared_kernel.job_package.checksum import compute_content_checksum


class TestComputeContentChecksum:
    """Tests for compute_content_checksum function.

    Scenario: Content checksum computation
    - Walk content/ directory recursively
    - Include only regular files matching [0-9a-f]+
    - Sort entries lexicographically by normalized path
    - For each file: path + '\\n' + file bytes
    - SHA-256 of the resulting stream
    """

    def test_empty_directory_produces_deterministic_checksum(self, tmp_path: Path):
        """An empty content/ directory always gives the same checksum."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        checksum1 = compute_content_checksum(content_dir)
        checksum2 = compute_content_checksum(content_dir)

        assert checksum1 == checksum2
        # Should be SHA-256 of empty stream: e3b0c44298...
        assert checksum1 == hashlib.sha256(b"").hexdigest()

    def test_single_file_checksum(self, tmp_path: Path):
        """Checksum of a single content file is reproducible."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        hex_name = hashlib.sha256(b"hello").hexdigest()
        (content_dir / hex_name).write_bytes(b"hello")

        checksum = compute_content_checksum(content_dir)

        # Manually compute expected: path + '\n' + bytes
        expected_hasher = hashlib.sha256()
        expected_hasher.update(hex_name.encode("utf-8"))
        expected_hasher.update(b"\n")
        expected_hasher.update(b"hello")
        assert checksum == expected_hasher.hexdigest()

    def test_order_independent(self, tmp_path: Path):
        """Files are sorted lexicographically, so insertion order doesn't matter."""
        content_dir1 = tmp_path / "c1"
        content_dir1.mkdir()
        content_dir2 = tmp_path / "c2"
        content_dir2.mkdir()

        file_a = "a" * 64
        file_b = "b" * 64
        data_a = b"alpha content"
        data_b = b"beta content"

        # Write in different orders
        (content_dir1 / file_a).write_bytes(data_a)
        (content_dir1 / file_b).write_bytes(data_b)

        (content_dir2 / file_b).write_bytes(data_b)
        (content_dir2 / file_a).write_bytes(data_a)

        checksum1 = compute_content_checksum(content_dir1)
        checksum2 = compute_content_checksum(content_dir2)

        assert checksum1 == checksum2

    def test_excludes_non_hex_files(self, tmp_path: Path):
        """Files not matching [0-9a-f]+ pattern are excluded from checksum."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        hex_name = hashlib.sha256(b"data").hexdigest()
        (content_dir / hex_name).write_bytes(b"data")
        (content_dir / "README.txt").write_bytes(b"ignore me")
        (content_dir / ".DS_Store").write_bytes(b"mac garbage")

        # Checksum with non-hex files should equal checksum with only hex file
        checksum_with_extras = compute_content_checksum(content_dir)

        clean_dir = tmp_path / "clean"
        clean_dir.mkdir()
        (clean_dir / hex_name).write_bytes(b"data")
        checksum_clean = compute_content_checksum(clean_dir)

        assert checksum_with_extras == checksum_clean

    def test_excludes_uppercase_hex_files(self, tmp_path: Path):
        """Files with uppercase hex chars are excluded (must be lowercase)."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        hex_lower = "a" * 64
        hex_upper = "A" * 64  # Not matching [0-9a-f]+
        (content_dir / hex_lower).write_bytes(b"lower")
        (content_dir / hex_upper).write_bytes(b"upper")

        checksum = compute_content_checksum(content_dir)

        # Should only include the lowercase file
        clean_dir = tmp_path / "clean"
        clean_dir.mkdir()
        (clean_dir / hex_lower).write_bytes(b"lower")
        expected = compute_content_checksum(clean_dir)

        assert checksum == expected

    def test_file_metadata_excluded(self, tmp_path: Path):
        """File timestamps/permissions do not affect the checksum."""
        content_dir1 = tmp_path / "c1"
        content_dir1.mkdir()
        content_dir2 = tmp_path / "c2"
        content_dir2.mkdir()

        hex_name = hashlib.sha256(b"same").hexdigest()
        file1 = content_dir1 / hex_name
        file2 = content_dir2 / hex_name
        file1.write_bytes(b"same")
        file2.write_bytes(b"same")

        # Deliberately modify timestamps to be different
        os.utime(file1, (1000000, 1000000))
        os.utime(file2, (2000000, 2000000))

        assert compute_content_checksum(content_dir1) == compute_content_checksum(
            content_dir2
        )

    def test_different_content_different_checksum(self, tmp_path: Path):
        """Different content produces different checksums."""
        content_dir1 = tmp_path / "c1"
        content_dir1.mkdir()
        content_dir2 = tmp_path / "c2"
        content_dir2.mkdir()

        hex_name = "a" * 64
        (content_dir1 / hex_name).write_bytes(b"content A")
        (content_dir2 / hex_name).write_bytes(b"content B")

        assert compute_content_checksum(content_dir1) != compute_content_checksum(
            content_dir2
        )

    def test_returns_hex_string(self, tmp_path: Path):
        """Checksum is a hex-encoded SHA-256 string (64 chars)."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        checksum = compute_content_checksum(content_dir)
        assert len(checksum) == 64
        assert re.match(r"^[0-9a-f]{64}$", checksum)

    def test_skips_directories(self, tmp_path: Path):
        """Subdirectories are not included as files."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # A subdirectory named with hex chars
        (content_dir / ("a" * 64)).mkdir()

        # Should not raise and should produce empty-stream checksum
        checksum = compute_content_checksum(content_dir)
        assert checksum == hashlib.sha256(b"").hexdigest()

    def test_symlink_within_content_included(self, tmp_path: Path):
        """Symlinks pointing within content/ are followed and included.

        Scenario: Content checksum — symlinks resolve to target within content root.
        """
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        hex_name = hashlib.sha256(b"real file").hexdigest()
        real_file = content_dir / hex_name
        real_file.write_bytes(b"real file")

        link_name = "0" * 64
        link = content_dir / link_name
        link.symlink_to(real_file)

        # Both the real file and in-tree symlink should be included
        checksum = compute_content_checksum(content_dir)

        # Build expected: sorted([hex_name, link_name]) each with real content
        entries = sorted(
            [
                (hex_name, b"real file"),
                (link_name, b"real file"),
            ]
        )
        expected_hasher = hashlib.sha256()
        for path_str, data in entries:
            expected_hasher.update(path_str.encode("utf-8"))
            expected_hasher.update(b"\n")
            expected_hasher.update(data)

        assert checksum == expected_hasher.hexdigest()

    def test_symlink_outside_content_skipped(self, tmp_path: Path):
        """Symlinks pointing outside content/ root are skipped."""
        outside = tmp_path / "secret"
        outside.write_bytes(b"secret data")

        content_dir = tmp_path / "content"
        content_dir.mkdir()

        link_name = "0" * 64
        (content_dir / link_name).symlink_to(outside)

        # Out-of-tree symlink skipped => same as empty directory
        checksum = compute_content_checksum(content_dir)
        assert checksum == hashlib.sha256(b"").hexdigest()
