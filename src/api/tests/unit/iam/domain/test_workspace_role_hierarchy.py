"""Unit tests for Workspace three-tier role hierarchy.

Spec: specs/iam/workspaces.spec.md

Requirement: Three-Tier Role Hierarchy
The system SHALL enforce a permission hierarchy across workspace roles.

Scenario: Admin permissions
  GIVEN a user with the `admin` role on a workspace
  THEN the user has `manage`, `edit`, and `view` permissions

Scenario: Editor permissions
  GIVEN a user with the `editor` role on a workspace
  THEN the user has `edit` and `view` permissions
  AND the user does NOT have `manage` permission

Scenario: Member permissions
  GIVEN a user with the `member` role on a workspace
  THEN the user has `view` permission only
  AND the user does NOT have `edit` or `manage` permissions
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from iam.domain.value_objects import WorkspaceRole


class TestWorkspaceRoleEnum:
    """Tests for WorkspaceRole enum — verifies the three-tier structure exists."""

    def test_admin_role_value_is_admin(self):
        """ADMIN role must have value 'admin' to match SpiceDB relation name."""
        assert WorkspaceRole.ADMIN == "admin"
        assert WorkspaceRole.ADMIN.value == "admin"

    def test_editor_role_value_is_editor(self):
        """EDITOR role must have value 'editor' to match SpiceDB relation name."""
        assert WorkspaceRole.EDITOR == "editor"
        assert WorkspaceRole.EDITOR.value == "editor"

    def test_member_role_value_is_member(self):
        """MEMBER role must have value 'member' to match SpiceDB relation name."""
        assert WorkspaceRole.MEMBER == "member"
        assert WorkspaceRole.MEMBER.value == "member"

    def test_exactly_three_roles_exist(self):
        """Workspace must have exactly three roles: ADMIN, EDITOR, MEMBER."""
        roles = list(WorkspaceRole)
        assert len(roles) == 3
        assert WorkspaceRole.ADMIN in roles
        assert WorkspaceRole.EDITOR in roles
        assert WorkspaceRole.MEMBER in roles

    def test_roles_are_ordered_by_privilege(self):
        """The roles should be orderable by privilege for clarity."""
        # Verify all three roles can coexist as distinct values
        role_values = {role.value for role in WorkspaceRole}
        assert role_values == {"admin", "editor", "member"}


@pytest.fixture
def workspace_schema_block() -> str:
    """Extract the workspace definition block from the SpiceDB schema."""
    schema_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "shared_kernel"
        / "authorization"
        / "spicedb"
        / "schema.zed"
    )
    assert schema_path.exists(), f"SpiceDB schema not found at {schema_path}"
    schema_text = schema_path.read_text()

    # Extract the workspace definition block
    match = re.search(
        r"definition workspace \{.*?\}",
        schema_text,
        re.DOTALL,
    )
    assert match is not None, "workspace definition not found in schema"
    return match.group(0)


class TestSpiceDBSchemaWorkspacePermissionHierarchy:
    """Schema contract tests for the workspace three-tier permission hierarchy.

    These tests verify the SpiceDB schema file correctly encodes the
    permission hierarchy specified in workspaces.spec.md, ensuring the
    schema cannot be accidentally changed in a way that breaks the spec.

    They parse schema.zed text rather than querying a live SpiceDB instance,
    so they run as pure unit tests with no infrastructure dependencies.
    """

    # --- Scenario: Admin permissions ---

    def test_admin_role_relation_is_defined(self, workspace_schema_block: str):
        """ADMIN role is defined as a relation on the workspace resource.

        GIVEN a user with the `admin` role on a workspace
        THEN the user has `manage`, `edit`, and `view` permissions (via admin relation)
        """
        assert "relation admin:" in workspace_schema_block

    def test_admin_grants_manage_permission(self, workspace_schema_block: str):
        """Admin relation is included in the `manage` permission.

        Scenario: Admin permissions
          THEN the user has `manage` permission
        """
        manage_match = re.search(
            r"permission manage\s*=\s*(.+)", workspace_schema_block
        )
        assert manage_match is not None, (
            "permission manage not found in workspace block"
        )
        manage_rhs = manage_match.group(1).strip()
        assert "admin" in manage_rhs, (
            f"'admin' should be in 'permission manage' but got: {manage_rhs}"
        )

    def test_admin_grants_edit_permission(self, workspace_schema_block: str):
        """Admin relation is included in the `edit` permission.

        Scenario: Admin permissions
          THEN the user has `edit` permission
        """
        edit_match = re.search(r"permission edit\s*=\s*(.+)", workspace_schema_block)
        assert edit_match is not None, "permission edit not found in workspace block"
        edit_rhs = edit_match.group(1).strip()
        assert "admin" in edit_rhs, (
            f"'admin' should be in 'permission edit' but got: {edit_rhs}"
        )

    def test_admin_grants_view_permission(self, workspace_schema_block: str):
        """Admin relation is included in the `view` permission.

        Scenario: Admin permissions
          THEN the user has `view` permission
        """
        view_match = re.search(r"permission view\s*=\s*(.+)", workspace_schema_block)
        assert view_match is not None, "permission view not found in workspace block"
        view_rhs = view_match.group(1).strip()
        assert "admin" in view_rhs, (
            f"'admin' should be in 'permission view' but got: {view_rhs}"
        )

    # --- Scenario: Editor permissions ---

    def test_editor_role_relation_is_defined(self, workspace_schema_block: str):
        """EDITOR role is defined as a relation on the workspace resource.

        Scenario: Editor permissions — the editor relation must exist.
        """
        assert "relation editor:" in workspace_schema_block

    def test_editor_grants_edit_permission(self, workspace_schema_block: str):
        """Editor relation is included in the `edit` permission.

        Scenario: Editor permissions
          THEN the user has `edit` permission
        """
        edit_match = re.search(r"permission edit\s*=\s*(.+)", workspace_schema_block)
        assert edit_match is not None
        edit_rhs = edit_match.group(1).strip()
        assert "editor" in edit_rhs, (
            f"'editor' should be in 'permission edit' but got: {edit_rhs}"
        )

    def test_editor_grants_view_permission(self, workspace_schema_block: str):
        """Editor relation is included in the `view` permission.

        Scenario: Editor permissions
          THEN the user has `view` permission
        """
        view_match = re.search(r"permission view\s*=\s*(.+)", workspace_schema_block)
        assert view_match is not None
        view_rhs = view_match.group(1).strip()
        assert "editor" in view_rhs, (
            f"'editor' should be in 'permission view' but got: {view_rhs}"
        )

    def test_editor_does_not_grant_manage_permission(self, workspace_schema_block: str):
        """Editor relation is NOT included in the `manage` permission.

        Scenario: Editor permissions
          AND the user does NOT have `manage` permission
        """
        manage_match = re.search(
            r"permission manage\s*=\s*(.+)", workspace_schema_block
        )
        assert manage_match is not None
        manage_rhs = manage_match.group(1).strip()
        # Tokenize — split on " + " and strip to get individual relations
        manage_relations = [r.strip() for r in manage_rhs.split("+")]
        assert "editor" not in manage_relations, (
            f"'editor' should NOT be in 'permission manage'. "
            f"Got relations: {manage_relations}"
        )

    # --- Scenario: Member permissions ---

    def test_member_role_relation_is_defined(self, workspace_schema_block: str):
        """MEMBER role is defined as a relation on the workspace resource.

        Scenario: Member permissions — the member relation must exist.
        """
        assert "relation member:" in workspace_schema_block

    def test_member_grants_view_permission(self, workspace_schema_block: str):
        """Member relation is included in the `view` permission.

        Scenario: Member permissions
          THEN the user has `view` permission
        """
        view_match = re.search(r"permission view\s*=\s*(.+)", workspace_schema_block)
        assert view_match is not None
        view_rhs = view_match.group(1).strip()
        assert "member" in view_rhs, (
            f"'member' should be in 'permission view' but got: {view_rhs}"
        )

    def test_member_does_not_grant_edit_permission(self, workspace_schema_block: str):
        """Member relation is NOT included in the `edit` permission.

        Scenario: Member permissions
          AND the user does NOT have `edit` permission
        """
        edit_match = re.search(r"permission edit\s*=\s*(.+)", workspace_schema_block)
        assert edit_match is not None
        edit_rhs = edit_match.group(1).strip()
        # Tokenize — split on " + " and strip to get individual relations
        edit_relations = [r.strip() for r in edit_rhs.split("+")]
        assert "member" not in edit_relations, (
            f"'member' should NOT be in 'permission edit'. "
            f"Got relations: {edit_relations}"
        )

    def test_member_does_not_grant_manage_permission(self, workspace_schema_block: str):
        """Member relation is NOT included in the `manage` permission.

        Scenario: Member permissions
          AND the user does NOT have `manage` permission
        """
        manage_match = re.search(
            r"permission manage\s*=\s*(.+)", workspace_schema_block
        )
        assert manage_match is not None
        manage_rhs = manage_match.group(1).strip()
        manage_relations = [r.strip() for r in manage_rhs.split("+")]
        assert "member" not in manage_relations, (
            f"'member' should NOT be in 'permission manage'. "
            f"Got relations: {manage_relations}"
        )

    # --- Bonus: Root workspace creator_tenant delegation ---

    def test_root_workspace_creator_tenant_enables_create_child(
        self, workspace_schema_block: str
    ):
        """Root workspaces delegate create_child to tenant members via creator_tenant.

        Spec: Root Workspace Scenario
          AND a `creator_tenant` relationship is established granting all tenant
          members the `create_child` permission
        """
        create_child_match = re.search(
            r"permission create_child\s*=\s*(.+)", workspace_schema_block
        )
        assert create_child_match is not None, (
            "permission create_child not found in workspace block"
        )
        create_child_rhs = create_child_match.group(1).strip()
        assert "creator_tenant" in create_child_rhs, (
            f"'creator_tenant' should be in 'permission create_child' but got: "
            f"{create_child_rhs}"
        )
        assert "view" in create_child_rhs, (
            f"'creator_tenant->view' delegation should be in 'permission create_child' "
            f"but got: {create_child_rhs}"
        )
