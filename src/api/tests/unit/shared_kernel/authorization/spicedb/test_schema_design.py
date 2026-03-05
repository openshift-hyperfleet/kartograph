"""SpiceDB Schema Design Tests.

Validates that the authorization schema encodes the correct permission rules.
These tests read the schema file directly and verify permission expressions,
ensuring schema changes are intentional and documented via tests.

Design principles verified by these tests:

1. Permission Composition: Permissions should compose other permissions
   (e.g., tenant->view) not relations (e.g., tenant->member). This is
   more maintainable and semantic. If tenant.view logic changes,
   workspace/group automatically inherit the change.

2. Organizational Visibility: Tenant members should have VIEW access to
   organizational resources (groups, workspaces) within their tenant for
   discovery and collaboration.

3. Explicit Grants Required: Write operations (edit, manage) require
   explicit role assignments, not just tenant membership.

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


@pytest.fixture
def schema() -> str:
    """Read the SpiceDB schema file."""
    assert SCHEMA_PATH.exists(), f"Schema file not found at {SCHEMA_PATH}"
    return SCHEMA_PATH.read_text()


class TestWorkspaceViewPermission:
    """Tests for workspace VIEW permission design.

    Workspace VIEW should be granted to:
    - Direct workspace members (admin, editor, member roles)
    - All tenant members (via tenant->view) for organizational visibility

    Uses tenant->view (permission composition) instead of tenant->member
    (relation) following SpiceDB best practices. Since tenant.view = admin +
    member, the end result is the same, but the schema is more maintainable.
    """

    def test_workspace_view_includes_tenant_member(self, schema: str):
        """Verify workspace view permission includes tenant->view.

        Tenant members should have VIEW access to all workspaces in their tenant
        for organizational visibility, without requiring per-workspace grants.
        Uses tenant->view (permission composition) instead of tenant->member
        (relation) following SpiceDB best practices.
        """
        view_expr = _extract_permission(schema, "workspace", "view")
        assert view_expr is not None, "workspace.view permission not found in schema"
        assert "tenant->view" in view_expr, (
            f"workspace.view should include 'tenant->view' for organizational visibility. "
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
        """Verify group view permission includes tenant->view (existing pattern).

        This test documents the existing pattern that workspace.view follows.
        Uses tenant->view (permission composition) instead of tenant->member
        (relation) following SpiceDB best practices.
        """
        view_expr = _extract_permission(schema, "group", "view")
        assert view_expr is not None, "group.view permission not found in schema"
        assert "tenant->view" in view_expr, (
            f"group.view should include 'tenant->view'. Current expression: {view_expr}"
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


class TestKnowledgeGraphSchemaDesign:
    """Tests for knowledge_graph permission design.

    Knowledge graphs sit within a workspace and inherit workspace-level access.
    Direct roles (admin, editor, viewer) allow fine-grained per-KG grants,
    while workspace arrow permissions (workspace->view, etc.) ensure that
    workspace members automatically gain access to knowledge graphs within
    that workspace.

    Permission model:
    - view  = admin + editor + viewer + workspace->view
    - edit  = admin + editor + workspace->edit
    - manage = admin + workspace->manage
    """

    def test_knowledge_graph_definition_exists(self, schema: str):
        """Verify the knowledge_graph definition block exists in the schema."""
        def_pattern = r"definition\s+knowledge_graph\s*\{"
        assert re.search(def_pattern, schema), (
            "definition knowledge_graph not found in schema"
        )

    def test_knowledge_graph_view_includes_workspace_view(self, schema: str):
        """Verify knowledge_graph view permission includes workspace->view.

        Workspace members should have VIEW access to all knowledge graphs
        within the workspace, without requiring per-KG grants.
        Knowledge graph visibility is scoped to workspace membership,
        NOT tenant-wide — unlike groups and workspaces which use tenant->view
        for organizational discoverability.
        """
        view_expr = _extract_permission(schema, "knowledge_graph", "view")
        assert view_expr is not None, (
            "knowledge_graph.view permission not found in schema"
        )
        assert "workspace->view" in view_expr, (
            f"knowledge_graph.view should include 'workspace->view' for "
            f"workspace-level visibility. Current expression: {view_expr}"
        )
        assert "tenant->view" not in view_expr, (
            f"knowledge_graph.view should NOT include 'tenant->view'. "
            f"KG visibility is scoped to workspace, not tenant-wide. "
            f"Current expression: {view_expr}"
        )

    def test_knowledge_graph_view_includes_direct_roles(self, schema: str):
        """Verify knowledge_graph view permission includes all direct roles."""
        view_expr = _extract_permission(schema, "knowledge_graph", "view")
        assert view_expr is not None, (
            "knowledge_graph.view permission not found in schema"
        )

        for role in ("admin", "editor", "viewer"):
            assert role in view_expr, (
                f"knowledge_graph.view should include '{role}'. "
                f"Current expression: {view_expr}"
            )

    def test_knowledge_graph_edit_includes_workspace_edit(self, schema: str):
        """Verify knowledge_graph edit permission includes workspace->edit.

        Workspace editors should have edit access to knowledge graphs within
        the workspace, without requiring per-KG grants.
        """
        edit_expr = _extract_permission(schema, "knowledge_graph", "edit")
        assert edit_expr is not None, (
            "knowledge_graph.edit permission not found in schema"
        )
        assert "workspace->edit" in edit_expr, (
            f"knowledge_graph.edit should include 'workspace->edit'. "
            f"Current expression: {edit_expr}"
        )

    def test_knowledge_graph_edit_includes_direct_roles(self, schema: str):
        """Verify knowledge_graph edit permission includes admin and editor."""
        edit_expr = _extract_permission(schema, "knowledge_graph", "edit")
        assert edit_expr is not None, (
            "knowledge_graph.edit permission not found in schema"
        )

        for role in ("admin", "editor"):
            assert role in edit_expr, (
                f"knowledge_graph.edit should include '{role}'. "
                f"Current expression: {edit_expr}"
            )

    def test_knowledge_graph_edit_excludes_viewer(self, schema: str):
        """Verify knowledge_graph edit permission does NOT include viewer.

        Viewers should only have read access. Edit requires explicit editor
        or admin grants.
        """
        edit_expr = _extract_permission(schema, "knowledge_graph", "edit")
        assert edit_expr is not None, (
            "knowledge_graph.edit permission not found in schema"
        )
        assert not re.search(r"\bviewer\b", edit_expr), (
            f"knowledge_graph.edit should NOT include 'viewer'. "
            f"Edit requires explicit editor or admin grants. "
            f"Current expression: {edit_expr}"
        )

    def test_knowledge_graph_manage_includes_workspace_manage(self, schema: str):
        """Verify knowledge_graph manage permission includes workspace->manage.

        Workspace admins should have manage access to knowledge graphs within
        the workspace, without requiring per-KG grants.
        """
        manage_expr = _extract_permission(schema, "knowledge_graph", "manage")
        assert manage_expr is not None, (
            "knowledge_graph.manage permission not found in schema"
        )
        assert "workspace->manage" in manage_expr, (
            f"knowledge_graph.manage should include 'workspace->manage'. "
            f"Current expression: {manage_expr}"
        )

    def test_knowledge_graph_manage_is_admin_based(self, schema: str):
        """Verify knowledge_graph manage permission is admin-only.

        Only admins (direct or via workspace) should have manage access.
        Editor and viewer roles must not appear in the manage expression.
        """
        manage_expr = _extract_permission(schema, "knowledge_graph", "manage")
        assert manage_expr is not None, (
            "knowledge_graph.manage permission not found in schema"
        )
        assert "admin" in manage_expr, (
            f"knowledge_graph.manage should include 'admin'. "
            f"Current expression: {manage_expr}"
        )
        for role in ("editor", "viewer"):
            assert role not in manage_expr, (
                f"knowledge_graph.manage should NOT include '{role}'. "
                f"Manage is admin-only. Current expression: {manage_expr}"
            )


class TestDataSourceSchemaDesign:
    """Tests for data_source permission design.

    Data sources belong to a knowledge graph and inherit all access through
    the KG relationship. There are no direct user/group relations on data
    sources — access is purely derived from the parent knowledge graph.

    Permission model:
    - view   = knowledge_graph->view
    - edit   = knowledge_graph->edit
    - manage = knowledge_graph->manage
    """

    def test_data_source_definition_exists(self, schema: str):
        """Verify the data_source definition block exists in the schema."""
        def_pattern = r"definition\s+data_source\s*\{"
        assert re.search(def_pattern, schema), (
            "definition data_source not found in schema"
        )

    def test_data_source_view_inherits_from_knowledge_graph(self, schema: str):
        """Verify data_source view permission is exactly knowledge_graph->view.

        Data source view access is entirely derived from the parent knowledge
        graph's view permission. No additional grants should be present.
        """
        view_expr = _extract_permission(schema, "data_source", "view")
        assert view_expr is not None, "data_source.view permission not found in schema"
        assert view_expr == "knowledge_graph->view", (
            f"data_source.view should be exactly 'knowledge_graph->view'. "
            f"Current expression: {view_expr}"
        )

    def test_data_source_edit_inherits_from_knowledge_graph(self, schema: str):
        """Verify data_source edit permission is exactly knowledge_graph->edit.

        Data source edit access is entirely derived from the parent knowledge
        graph's edit permission. No additional grants should be present.
        """
        edit_expr = _extract_permission(schema, "data_source", "edit")
        assert edit_expr is not None, "data_source.edit permission not found in schema"
        assert edit_expr == "knowledge_graph->edit", (
            f"data_source.edit should be exactly 'knowledge_graph->edit'. "
            f"Current expression: {edit_expr}"
        )

    def test_data_source_manage_inherits_from_knowledge_graph(self, schema: str):
        """Verify data_source manage permission is exactly knowledge_graph->manage.

        Data source manage access is entirely derived from the parent knowledge
        graph's manage permission. No additional grants should be present.
        """
        manage_expr = _extract_permission(schema, "data_source", "manage")
        assert manage_expr is not None, (
            "data_source.manage permission not found in schema"
        )
        assert manage_expr == "knowledge_graph->manage", (
            f"data_source.manage should be exactly 'knowledge_graph->manage'. "
            f"Current expression: {manage_expr}"
        )

    def test_data_source_has_no_direct_user_relations(self, schema: str):
        """Verify data_source has no direct user role relations.

        Data sources should not have admin, editor, or viewer relations
        pointing to users. All access is inherited through the knowledge
        graph relationship.
        """
        def_pattern = r"definition\s+data_source\s*\{(.*?)\n\}"
        def_match = re.search(def_pattern, schema, re.DOTALL)
        assert def_match is not None, "definition data_source not found in schema"

        def_body = def_match.group(1)
        for role in ("admin", "editor", "viewer"):
            assert not re.search(rf"relation\s+{role}\s*:", def_body), (
                f"data_source should NOT have a direct '{role}' relation. "
                f"All access should be inherited through knowledge_graph."
            )
