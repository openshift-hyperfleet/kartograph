"""Integration tests for Knowledge Graph authorization enforcement.

Tests the ReBAC permission model for knowledge graphs, verifying both
workspace-inherited access and direct-grant scenarios as defined in:
specs/iam/authorization.spec.md — Requirement: Knowledge Graph Permissions

Permission model (from schema.zed):
    knowledge_graph.view   = admin + editor + viewer + workspace->view
    knowledge_graph.edit   = admin + editor + workspace->edit
    knowledge_graph.manage = admin + workspace->manage

These tests write SpiceDB relationships directly (bypassing the REST API,
which does not yet expose management endpoints) to validate that the
authorization schema correctly computes permissions across resource
hierarchies.

Spec-Ref: specs/iam/authorization.spec.md@774c6c8eb35f1f3d4226385ff483f4e5dc344a08
Task-Ref: task-023
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from infrastructure.authorization_dependencies import get_spicedb_client
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    RelationType,
    ResourceType,
    format_resource,
    format_subject,
)

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def spicedb_client() -> AuthorizationProvider:
    """Provide a SpiceDB client for authorization integration tests."""
    return get_spicedb_client()


@pytest.fixture
def user_id() -> str:
    """Unique user ID for this test to prevent cross-test pollution."""
    return f"test-user-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def workspace_id() -> str:
    """Unique workspace ID for this test."""
    return f"test-ws-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def kg_id() -> str:
    """Unique knowledge graph ID for this test."""
    return f"test-kg-{uuid.uuid4().hex[:12]}"


@pytest_asyncio.fixture(autouse=True)
async def cleanup_spicedb_relationships(
    spicedb_client: AuthorizationProvider,
    user_id: str,
    workspace_id: str,
    kg_id: str,
):
    """Remove any SpiceDB relationships created during the test.

    Runs as autouse fixture to guarantee cleanup even on test failure.
    Suppresses errors on deletion of non-existent relationships.
    """
    yield

    # Clean up relationships that may have been created during the test.
    # We use delete_relationships_by_filter to remove all relationships
    # for the test resources without knowing exact tuples.
    try:
        # Remove all relationships for the test knowledge graph
        await spicedb_client.delete_relationships_by_filter(
            resource_type=ResourceType.KNOWLEDGE_GRAPH,
            resource_id=kg_id,
            relation=None,
            subject_type=None,
            subject_id=None,
        )
    except Exception:
        pass

    try:
        # Remove all relationships for the test workspace
        await spicedb_client.delete_relationships_by_filter(
            resource_type=ResourceType.WORKSPACE,
            resource_id=workspace_id,
            relation=None,
            subject_type=None,
            subject_id=None,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Requirement: Knowledge Graph Permissions
# Scenario: Workspace-inherited access
#
# GIVEN a knowledge graph associated with a workspace
# AND a user with `edit` permission on the workspace
# THEN the user has `edit` and `view` permissions on the knowledge graph
# ---------------------------------------------------------------------------


class TestWorkspaceInheritedKnowledgeGraphAccess:
    """Tests for workspace-inherited KG access via SpiceDB ReBAC chain.

    Verifies: knowledge_graph.view = workspace->view
              knowledge_graph.edit = workspace->edit
    """

    @pytest.mark.asyncio
    async def test_workspace_editor_can_view_knowledge_graph(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        workspace_id: str,
        kg_id: str,
    ):
        """Workspace editor should have VIEW permission on knowledge graph.

        Authorization chain:
          knowledge_graph:kg → workspace:ws (relation: workspace)
          workspace:ws → user:u (relation: editor)
          workspace.view = admin + editor + member + tenant->view
          knowledge_graph.view = admin + editor + viewer + workspace->view
          ∴ user:u has VIEW on knowledge_graph:kg
        """
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        ws_resource = format_resource(ResourceType.WORKSPACE, workspace_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        # Link kg to workspace
        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.WORKSPACE,
            subject=ws_resource,
        )
        # Grant user editor on workspace
        await spicedb_client.write_relationship(
            resource=ws_resource,
            relation=RelationType.EDITOR,
            subject=user_subject,
        )

        has_view = await spicedb_client.check_permission(
            resource=kg_resource,
            permission=Permission.VIEW,
            subject=user_subject,
        )
        assert has_view is True, (
            "Workspace editor should have VIEW permission on knowledge graph "
            "via workspace->view inheritance"
        )

    @pytest.mark.asyncio
    async def test_workspace_editor_can_edit_knowledge_graph(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        workspace_id: str,
        kg_id: str,
    ):
        """Workspace editor should have EDIT permission on knowledge graph.

        Authorization chain:
          knowledge_graph.edit = admin + editor + workspace->edit
          workspace.edit = admin + editor
          user:u has editor on workspace:ws → workspace->edit satisfied
          ∴ user:u has EDIT on knowledge_graph:kg
        """
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        ws_resource = format_resource(ResourceType.WORKSPACE, workspace_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.WORKSPACE,
            subject=ws_resource,
        )
        await spicedb_client.write_relationship(
            resource=ws_resource,
            relation=RelationType.EDITOR,
            subject=user_subject,
        )

        has_edit = await spicedb_client.check_permission(
            resource=kg_resource,
            permission=Permission.EDIT,
            subject=user_subject,
        )
        assert has_edit is True, (
            "Workspace editor should have EDIT permission on knowledge graph "
            "via workspace->edit inheritance"
        )

    @pytest.mark.asyncio
    async def test_workspace_editor_cannot_manage_knowledge_graph(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        workspace_id: str,
        kg_id: str,
    ):
        """Workspace editor should NOT have MANAGE permission on knowledge graph.

        knowledge_graph.manage = admin + workspace->manage
        workspace.manage = admin (only)
        Workspace editor does NOT satisfy workspace->manage.
        """
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        ws_resource = format_resource(ResourceType.WORKSPACE, workspace_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.WORKSPACE,
            subject=ws_resource,
        )
        await spicedb_client.write_relationship(
            resource=ws_resource,
            relation=RelationType.EDITOR,
            subject=user_subject,
        )

        has_manage = await spicedb_client.check_permission(
            resource=kg_resource,
            permission=Permission.MANAGE,
            subject=user_subject,
        )
        assert has_manage is False, (
            "Workspace editor should NOT have MANAGE permission on knowledge graph. "
            "MANAGE requires admin or workspace->manage (admin-only)."
        )

    @pytest.mark.asyncio
    async def test_workspace_admin_can_manage_knowledge_graph(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        workspace_id: str,
        kg_id: str,
    ):
        """Workspace admin should have MANAGE permission on knowledge graph.

        knowledge_graph.manage = admin + workspace->manage
        workspace.manage = admin
        workspace admin → workspace->manage → knowledge_graph.manage satisfied.
        """
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        ws_resource = format_resource(ResourceType.WORKSPACE, workspace_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.WORKSPACE,
            subject=ws_resource,
        )
        await spicedb_client.write_relationship(
            resource=ws_resource,
            relation=RelationType.ADMIN,
            subject=user_subject,
        )

        has_manage = await spicedb_client.check_permission(
            resource=kg_resource,
            permission=Permission.MANAGE,
            subject=user_subject,
        )
        assert has_manage is True, (
            "Workspace admin should have MANAGE permission on knowledge graph "
            "via workspace->manage inheritance"
        )

    @pytest.mark.asyncio
    async def test_workspace_member_can_view_knowledge_graph(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        workspace_id: str,
        kg_id: str,
    ):
        """Workspace member (view-only) should have VIEW permission on knowledge graph.

        workspace.view = admin + editor + member + tenant->view
        knowledge_graph.view = admin + editor + viewer + workspace->view
        workspace member → workspace->view → knowledge_graph.view satisfied.
        """
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        ws_resource = format_resource(ResourceType.WORKSPACE, workspace_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.WORKSPACE,
            subject=ws_resource,
        )
        await spicedb_client.write_relationship(
            resource=ws_resource,
            relation=RelationType.MEMBER,
            subject=user_subject,
        )

        has_view = await spicedb_client.check_permission(
            resource=kg_resource,
            permission=Permission.VIEW,
            subject=user_subject,
        )
        assert has_view is True, (
            "Workspace member should have VIEW permission on knowledge graph "
            "via workspace->view inheritance"
        )

    @pytest.mark.asyncio
    async def test_workspace_member_cannot_edit_knowledge_graph(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        workspace_id: str,
        kg_id: str,
    ):
        """Workspace member should NOT have EDIT permission on knowledge graph.

        knowledge_graph.edit = admin + editor + workspace->edit
        workspace.edit = admin + editor  (member excluded)
        Workspace member does NOT satisfy workspace->edit.
        """
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        ws_resource = format_resource(ResourceType.WORKSPACE, workspace_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.WORKSPACE,
            subject=ws_resource,
        )
        await spicedb_client.write_relationship(
            resource=ws_resource,
            relation=RelationType.MEMBER,
            subject=user_subject,
        )

        has_edit = await spicedb_client.check_permission(
            resource=kg_resource,
            permission=Permission.EDIT,
            subject=user_subject,
        )
        assert has_edit is False, (
            "Workspace member should NOT have EDIT permission on knowledge graph. "
            "EDIT requires admin, editor, or workspace->edit (which requires admin/editor)."
        )

    @pytest.mark.asyncio
    async def test_user_without_workspace_role_cannot_access_knowledge_graph(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        workspace_id: str,
        kg_id: str,
    ):
        """User with no workspace relationship should have no KG access.

        Without any relationship to the workspace or KG, all permissions
        should be denied.
        """
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        ws_resource = format_resource(ResourceType.WORKSPACE, workspace_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        # Only create the KG→workspace relationship, no user grant
        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.WORKSPACE,
            subject=ws_resource,
        )
        # Deliberately do NOT grant user any workspace role

        for permission in (Permission.VIEW, Permission.EDIT, Permission.MANAGE):
            has_perm = await spicedb_client.check_permission(
                resource=kg_resource,
                permission=permission,
                subject=user_subject,
            )
            assert has_perm is False, (
                f"User with no workspace relationship should NOT have {permission} "
                f"on knowledge graph"
            )


# ---------------------------------------------------------------------------
# Requirement: Knowledge Graph Permissions
# Scenario: Direct grant
#
# GIVEN a user with a direct `admin` role on a knowledge graph
# THEN the user has `manage`, `edit`, and `view` permissions on the KG
# ---------------------------------------------------------------------------


class TestDirectGrantKnowledgeGraphAccess:
    """Tests for direct role grants on knowledge graphs.

    Verifies that direct admin/editor/viewer grants on a knowledge graph
    work independently of workspace inheritance.
    """

    @pytest.mark.asyncio
    async def test_direct_kg_admin_has_manage_permission(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        kg_id: str,
    ):
        """Direct KG admin should have MANAGE permission.

        knowledge_graph.manage = admin + workspace->manage
        Direct admin grant → MANAGE satisfied without workspace inheritance.
        """
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.ADMIN,
            subject=user_subject,
        )

        has_manage = await spicedb_client.check_permission(
            resource=kg_resource,
            permission=Permission.MANAGE,
            subject=user_subject,
        )
        assert has_manage is True, "Direct KG admin should have MANAGE permission"

    @pytest.mark.asyncio
    async def test_direct_kg_admin_has_edit_permission(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        kg_id: str,
    ):
        """Direct KG admin should have EDIT permission.

        knowledge_graph.edit = admin + editor + workspace->edit
        """
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.ADMIN,
            subject=user_subject,
        )

        has_edit = await spicedb_client.check_permission(
            resource=kg_resource,
            permission=Permission.EDIT,
            subject=user_subject,
        )
        assert has_edit is True, "Direct KG admin should have EDIT permission"

    @pytest.mark.asyncio
    async def test_direct_kg_admin_has_view_permission(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        kg_id: str,
    ):
        """Direct KG admin should have VIEW permission.

        knowledge_graph.view = admin + editor + viewer + workspace->view
        """
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.ADMIN,
            subject=user_subject,
        )

        has_view = await spicedb_client.check_permission(
            resource=kg_resource,
            permission=Permission.VIEW,
            subject=user_subject,
        )
        assert has_view is True, "Direct KG admin should have VIEW permission"

    @pytest.mark.asyncio
    async def test_direct_kg_editor_has_edit_and_view_but_not_manage(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        kg_id: str,
    ):
        """Direct KG editor should have EDIT and VIEW but not MANAGE.

        knowledge_graph.edit = admin + editor + workspace->edit  → editor satisfies
        knowledge_graph.view = admin + editor + viewer + workspace->view  → editor satisfies
        knowledge_graph.manage = admin + workspace->manage  → editor does NOT satisfy
        """
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.EDITOR,
            subject=user_subject,
        )

        has_edit = await spicedb_client.check_permission(
            resource=kg_resource,
            permission=Permission.EDIT,
            subject=user_subject,
        )
        has_view = await spicedb_client.check_permission(
            resource=kg_resource,
            permission=Permission.VIEW,
            subject=user_subject,
        )
        has_manage = await spicedb_client.check_permission(
            resource=kg_resource,
            permission=Permission.MANAGE,
            subject=user_subject,
        )

        assert has_edit is True, "Direct KG editor should have EDIT permission"
        assert has_view is True, "Direct KG editor should have VIEW permission"
        assert has_manage is False, (
            "Direct KG editor should NOT have MANAGE permission (admin-only)"
        )

    @pytest.mark.asyncio
    async def test_direct_kg_viewer_has_view_only(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        kg_id: str,
    ):
        """Direct KG viewer should have VIEW but not EDIT or MANAGE.

        knowledge_graph.view = admin + editor + viewer + workspace->view  → viewer satisfies
        knowledge_graph.edit = admin + editor + workspace->edit  → viewer does NOT satisfy
        """
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.VIEWER,
            subject=user_subject,
        )

        has_view = await spicedb_client.check_permission(
            resource=kg_resource,
            permission=Permission.VIEW,
            subject=user_subject,
        )
        has_edit = await spicedb_client.check_permission(
            resource=kg_resource,
            permission=Permission.EDIT,
            subject=user_subject,
        )
        has_manage = await spicedb_client.check_permission(
            resource=kg_resource,
            permission=Permission.MANAGE,
            subject=user_subject,
        )

        assert has_view is True, "Direct KG viewer should have VIEW permission"
        assert has_edit is False, "Direct KG viewer should NOT have EDIT permission"
        assert has_manage is False, "Direct KG viewer should NOT have MANAGE permission"
