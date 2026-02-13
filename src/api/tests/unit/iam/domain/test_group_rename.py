"""Unit tests for Group.rename() aggregate method.

Tests the domain logic for renaming groups.
"""

from __future__ import annotations

import pytest

from iam.domain.aggregates import Group
from iam.domain.value_objects import GroupId, TenantId


class TestGroupRename:
    """Tests for Group.rename()."""

    def test_renames_group_successfully(self):
        """Should update the group name."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )

        group.rename("Platform Engineering")

        assert group.name == "Platform Engineering"

    def test_raises_value_error_for_empty_name(self):
        """Should raise ValueError for empty name."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )

        with pytest.raises(ValueError):
            group.rename("")

    def test_raises_value_error_for_too_long_name(self):
        """Should raise ValueError for name exceeding 255 characters."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )

        with pytest.raises(ValueError):
            group.rename("x" * 256)

    def test_raises_value_error_for_same_name(self):
        """Should raise ValueError when name hasn't changed."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )

        with pytest.raises(ValueError, match="same"):
            group.rename("Engineering")
