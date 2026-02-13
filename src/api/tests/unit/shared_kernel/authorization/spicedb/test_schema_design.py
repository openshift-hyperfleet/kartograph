"""Tests for SpiceDB schema design intent.

Validates that the authorization schema encodes the correct permission rules.
These tests read the schema file directly and verify permission expressions,
ensuring schema changes are intentional and documented via tests.

Following TDD - these tests define the desired authorization behavior
before the schema is updated.
"""

import re
from pathlib import Path

import pytest


SCHEMA_PATH = (
    Path(__file__).resolve().parents[5]
    / "shared_kernel"
    / "authorization"
    / "spicedb"
    / "schema.zed"
)


def _extract_permission(schema: str, definition: str, permission: str) -> str | None:
    """Extract a permission expression from a SpiceDB schema definition.

    Parses the schema text to find a specific permission within a definition block
    and returns the expression (right-hand side of the '=' sign).

    Args:
        schema: The full schema text.
        definition: The definition name (e.g., "workspace").
        permission: The permission name (e.g., "view").

    Returns:
        The permission expression string, or None if not found.
    """
    # Find the definition block
    def_pattern = rf"definition\s+{re.escape(definition)}\s*\{{(.*?)\n\}}"
    def_match = re.search(def_pattern, schema, re.DOTALL)
    if not def_match:
        return None

    def_body = def_match.group(1)

    # Find the permission line within the definition
    perm_pattern = rf"permission\s+{re.escape(permission)}\s*=\s*(.+)"
    perm_match = re.search(perm_pattern, def_body)
    if not perm_match:
        return None

    return perm_match.group(1).strip()


class TestWorkspaceViewPermission:
    """Tests for workspace VIEW permission design.

    Workspace VIEW should be granted to:
    - Direct workspace members (admin, editor, member roles)
    - All tenant members (tenant->member) for organizational visibility

    This follows the same pattern as group.view which includes tenant->member,
    ensuring tenant members can discover workspaces and request access.
    """

    @pytest.fixture
    def schema(self) -> str:
        """Read the SpiceDB schema file."""
        assert SCHEMA_PATH.exists(), f"Schema file not found at {SCHEMA_PATH}"
        return SCHEMA_PATH.read_text()

    def test_workspace_view_includes_tenant_member(self, schema: str):
        """Verify workspace view permission includes tenant->member.

        Tenant members should have VIEW access to all workspaces in their tenant
        for organizational visibility, without requiring per-workspace grants.
        This mirrors the group.view pattern (tenant->member).
        """
        view_expr = _extract_permission(schema, "workspace", "view")
        assert view_expr is not None, "workspace.view permission not found in schema"
        assert "tenant->member" in view_expr, (
            f"workspace.view should include 'tenant->member' for organizational visibility. "
            f"Current expression: {view_expr}"
        )

    def test_workspace_view_includes_direct_roles(self, schema: str):
        """Verify workspace view permission includes all direct workspace roles."""
        view_expr = _extract_permission(schema, "workspace", "view")
        assert view_expr is not None, "workspace.view permission not found in schema"

        for role in ("admin", "editor", "member"):
            assert role in view_expr, (
                f"workspace.view should include '{role}'. "
                f"Current expression: {view_expr}"
            )

    def test_group_view_includes_tenant_member(self, schema: str):
        """Verify group view permission includes tenant->member (existing pattern).

        This test documents the existing pattern that workspace.view should follow.
        """
        view_expr = _extract_permission(schema, "group", "view")
        assert view_expr is not None, "group.view permission not found in schema"
        assert "tenant->member" in view_expr, (
            f"group.view should include 'tenant->member'. "
            f"Current expression: {view_expr}"
        )

    def test_workspace_edit_excludes_tenant_member(self, schema: str):
        """Verify workspace edit permission does NOT include tenant->member.

        Tenant membership should only grant VIEW (read-only), not edit access.
        Edit requires explicit workspace-level grants.
        """
        edit_expr = _extract_permission(schema, "workspace", "edit")
        assert edit_expr is not None, "workspace.edit permission not found in schema"
        assert "tenant->member" not in edit_expr, (
            f"workspace.edit should NOT include 'tenant->member'. "
            f"Edit requires explicit workspace-level grants. "
            f"Current expression: {edit_expr}"
        )

    def test_workspace_manage_excludes_tenant_member(self, schema: str):
        """Verify workspace manage permission does NOT include tenant->member.

        Tenant membership should only grant VIEW (read-only), not manage access.
        Manage requires explicit admin grants.
        """
        manage_expr = _extract_permission(schema, "workspace", "manage")
        assert manage_expr is not None, (
            "workspace.manage permission not found in schema"
        )
        assert "tenant->member" not in manage_expr, (
            f"workspace.manage should NOT include 'tenant->member'. "
            f"Manage requires explicit admin grants. "
            f"Current expression: {manage_expr}"
        )
