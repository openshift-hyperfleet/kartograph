"""Integration tests for Data Source authorization enforcement.

Tests the ReBAC permission model for data sources, verifying that all
access is inherited purely from the parent knowledge graph as defined in:
specs/iam/authorization.spec.md — Requirement: Data Source Permissions

Permission model (from schema.zed):
    data_source.view   = knowledge_graph->view
    data_source.edit   = knowledge_graph->edit
    data_source.manage = knowledge_graph->manage

Data sources have no direct user/group relations. All access is derived
from the parent knowledge graph relationship. This test file verifies the
complete inheritance chain:

    user → workspace → knowledge_graph → data_source

These tests write SpiceDB relationships directly (bypassing the REST API,
which does not yet expose management endpoints) to validate that the
authorization schema correctly computes permissions across the full chain.

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


@pytest.fixture
def ds_id() -> str:
    """Unique data source ID for this test."""
    return f"test-ds-{uuid.uuid4().hex[:12]}"


@pytest_asyncio.fixture(autouse=True)
async def cleanup_spicedb_relationships(
    spicedb_client: AuthorizationProvider,
    user_id: str,
    workspace_id: str,
    kg_id: str,
    ds_id: str,
):
    """Remove any SpiceDB relationships created during the test.

    Runs as autouse fixture to guarantee cleanup even on test failure.
    """
    yield

    # Clean up all relationships for test resources
    for resource_type, resource_id in [
        (ResourceType.DATA_SOURCE, ds_id),
        (ResourceType.KNOWLEDGE_GRAPH, kg_id),
        (ResourceType.WORKSPACE, workspace_id),
    ]:
        try:
            await spicedb_client.delete_relationships_by_filter(
                resource_type=resource_type,
                resource_id=resource_id,
                relation=None,
                subject_type=None,
                subject_id=None,
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Requirement: Data Source Permissions
# Scenario: Inherited access
#
# GIVEN a data source belonging to a knowledge graph
# AND a user with `edit` permission on the knowledge graph
# THEN the user has `edit` and `view` permissions on the data source
# ---------------------------------------------------------------------------


class TestDataSourceInheritedFromKnowledgeGraph:
    """Tests for data source permission inheritance from the parent knowledge graph.

    The full inheritance chain:
        user → workspace (role) → knowledge_graph (via workspace relation)
        → data_source (via knowledge_graph relation)

    Or with a direct KG grant:
        user → knowledge_graph (direct role)
        → data_source (via knowledge_graph relation)
    """

    @pytest.mark.asyncio
    async def test_kg_editor_can_view_data_source(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        workspace_id: str,
        kg_id: str,
        ds_id: str,
    ):
        """KG editor should have VIEW permission on data source.

        Chain: user has editor on workspace
               workspace→view propagates to kg.view
               kg.view propagates to data_source.view (= knowledge_graph->view)
        """
        ds_resource = format_resource(ResourceType.DATA_SOURCE, ds_id)
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        ws_resource = format_resource(ResourceType.WORKSPACE, workspace_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        # Build the chain: DS → KG → WS → user:editor
        await spicedb_client.write_relationship(
            resource=ds_resource,
            relation=RelationType.KNOWLEDGE_GRAPH,
            subject=kg_resource,
        )
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

        has_view = await spicedb_client.check_permission(
            resource=ds_resource,
            permission=Permission.VIEW,
            subject=user_subject,
        )
        assert has_view is True, (
            "KG editor (via workspace) should have VIEW on data source "
            "via data_source.view = knowledge_graph->view chain"
        )

    @pytest.mark.asyncio
    async def test_kg_editor_can_edit_data_source(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        workspace_id: str,
        kg_id: str,
        ds_id: str,
    ):
        """KG editor should have EDIT permission on data source.

        data_source.edit = knowledge_graph->edit
        knowledge_graph.edit = admin + editor + workspace->edit
        workspace editor → workspace->edit → knowledge_graph->edit → data_source.edit
        """
        ds_resource = format_resource(ResourceType.DATA_SOURCE, ds_id)
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        ws_resource = format_resource(ResourceType.WORKSPACE, workspace_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=ds_resource,
            relation=RelationType.KNOWLEDGE_GRAPH,
            subject=kg_resource,
        )
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
            resource=ds_resource,
            permission=Permission.EDIT,
            subject=user_subject,
        )
        assert has_edit is True, (
            "KG editor (via workspace) should have EDIT on data source "
            "via data_source.edit = knowledge_graph->edit chain"
        )

    @pytest.mark.asyncio
    async def test_workspace_member_can_view_data_source(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        workspace_id: str,
        kg_id: str,
        ds_id: str,
    ):
        """Workspace member (view-only) should have VIEW permission on data source.

        workspace member → workspace->view → knowledge_graph.view satisfied
        data_source.view = knowledge_graph->view → data_source VIEW satisfied
        """
        ds_resource = format_resource(ResourceType.DATA_SOURCE, ds_id)
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        ws_resource = format_resource(ResourceType.WORKSPACE, workspace_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=ds_resource,
            relation=RelationType.KNOWLEDGE_GRAPH,
            subject=kg_resource,
        )
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
            resource=ds_resource,
            permission=Permission.VIEW,
            subject=user_subject,
        )
        assert has_view is True, (
            "Workspace member should have VIEW on data source "
            "via member→workspace->view→knowledge_graph->view chain"
        )

    @pytest.mark.asyncio
    async def test_workspace_member_cannot_edit_data_source(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        workspace_id: str,
        kg_id: str,
        ds_id: str,
    ):
        """Workspace member should NOT have EDIT permission on data source.

        data_source.edit = knowledge_graph->edit
        knowledge_graph.edit = admin + editor + workspace->edit
        workspace.edit = admin + editor  (member excluded)
        Workspace member does NOT satisfy any EDIT path.
        """
        ds_resource = format_resource(ResourceType.DATA_SOURCE, ds_id)
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        ws_resource = format_resource(ResourceType.WORKSPACE, workspace_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=ds_resource,
            relation=RelationType.KNOWLEDGE_GRAPH,
            subject=kg_resource,
        )
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
            resource=ds_resource,
            permission=Permission.EDIT,
            subject=user_subject,
        )
        assert has_edit is False, (
            "Workspace member should NOT have EDIT on data source. "
            "EDIT requires admin or editor (via workspace or direct KG grant)."
        )

    @pytest.mark.asyncio
    async def test_workspace_admin_can_manage_data_source(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        workspace_id: str,
        kg_id: str,
        ds_id: str,
    ):
        """Workspace admin should have MANAGE permission on data source.

        data_source.manage = knowledge_graph->manage
        knowledge_graph.manage = admin + workspace->manage
        workspace.manage = admin
        workspace admin → workspace->manage → knowledge_graph->manage → ds.manage
        """
        ds_resource = format_resource(ResourceType.DATA_SOURCE, ds_id)
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        ws_resource = format_resource(ResourceType.WORKSPACE, workspace_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=ds_resource,
            relation=RelationType.KNOWLEDGE_GRAPH,
            subject=kg_resource,
        )
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
            resource=ds_resource,
            permission=Permission.MANAGE,
            subject=user_subject,
        )
        assert has_manage is True, (
            "Workspace admin should have MANAGE on data source "
            "via admin→workspace->manage→knowledge_graph->manage chain"
        )

    @pytest.mark.asyncio
    async def test_user_without_kg_access_cannot_view_data_source(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        workspace_id: str,
        kg_id: str,
        ds_id: str,
    ):
        """User with no KG or workspace access should have no data source access.

        Without any relationship to the KG hierarchy, all permissions
        on the data source should be denied.
        """
        ds_resource = format_resource(ResourceType.DATA_SOURCE, ds_id)
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        ws_resource = format_resource(ResourceType.WORKSPACE, workspace_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        # Set up the DS→KG→WS chain but grant NO user relationship
        await spicedb_client.write_relationship(
            resource=ds_resource,
            relation=RelationType.KNOWLEDGE_GRAPH,
            subject=kg_resource,
        )
        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.WORKSPACE,
            subject=ws_resource,
        )
        # Deliberately do NOT grant user any role on workspace or KG

        for permission in (Permission.VIEW, Permission.EDIT, Permission.MANAGE):
            has_perm = await spicedb_client.check_permission(
                resource=ds_resource,
                permission=permission,
                subject=user_subject,
            )
            assert has_perm is False, (
                f"User with no access should NOT have {permission} on data source"
            )


class TestDataSourceDirectKGGrantInheritance:
    """Tests for data source access inherited from direct KG grants.

    Verifies that direct grants on the knowledge graph (not via workspace)
    also propagate to data source permissions.
    """

    @pytest.mark.asyncio
    async def test_direct_kg_editor_can_view_and_edit_data_source(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        kg_id: str,
        ds_id: str,
    ):
        """User with direct editor grant on KG should have VIEW and EDIT on DS.

        knowledge_graph editor → knowledge_graph.edit and .view satisfied
        data_source.view = knowledge_graph->view → satisfied
        data_source.edit = knowledge_graph->edit → satisfied
        """
        ds_resource = format_resource(ResourceType.DATA_SOURCE, ds_id)
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        # DS → KG chain
        await spicedb_client.write_relationship(
            resource=ds_resource,
            relation=RelationType.KNOWLEDGE_GRAPH,
            subject=kg_resource,
        )
        # Direct editor grant on KG (no workspace needed)
        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.EDITOR,
            subject=user_subject,
        )

        has_view = await spicedb_client.check_permission(
            resource=ds_resource,
            permission=Permission.VIEW,
            subject=user_subject,
        )
        has_edit = await spicedb_client.check_permission(
            resource=ds_resource,
            permission=Permission.EDIT,
            subject=user_subject,
        )
        has_manage = await spicedb_client.check_permission(
            resource=ds_resource,
            permission=Permission.MANAGE,
            subject=user_subject,
        )

        assert has_view is True, "Direct KG editor should have VIEW on data source"
        assert has_edit is True, "Direct KG editor should have EDIT on data source"
        assert has_manage is False, (
            "Direct KG editor should NOT have MANAGE on data source (admin-only)"
        )

    @pytest.mark.asyncio
    async def test_direct_kg_admin_has_full_data_source_access(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        kg_id: str,
        ds_id: str,
    ):
        """User with direct admin grant on KG should have full access on DS.

        knowledge_graph admin → knowledge_graph.manage, .edit, .view all satisfied
        data_source.view, .edit, .manage = knowledge_graph->* → all satisfied
        """
        ds_resource = format_resource(ResourceType.DATA_SOURCE, ds_id)
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=ds_resource,
            relation=RelationType.KNOWLEDGE_GRAPH,
            subject=kg_resource,
        )
        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.ADMIN,
            subject=user_subject,
        )

        for permission in (Permission.VIEW, Permission.EDIT, Permission.MANAGE):
            has_perm = await spicedb_client.check_permission(
                resource=ds_resource,
                permission=permission,
                subject=user_subject,
            )
            assert has_perm is True, (
                f"Direct KG admin should have {permission} on data source"
            )

    @pytest.mark.asyncio
    async def test_direct_kg_viewer_can_view_but_not_edit_data_source(
        self,
        spicedb_client: AuthorizationProvider,
        user_id: str,
        kg_id: str,
        ds_id: str,
    ):
        """User with direct viewer grant on KG should have VIEW only on DS.

        knowledge_graph.view = admin + editor + viewer + workspace->view → viewer satisfies
        knowledge_graph.edit = admin + editor + workspace->edit → viewer does NOT satisfy
        data_source.view = knowledge_graph->view → satisfied
        data_source.edit = knowledge_graph->edit → NOT satisfied
        """
        ds_resource = format_resource(ResourceType.DATA_SOURCE, ds_id)
        kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        user_subject = format_subject(ResourceType.USER, user_id)

        await spicedb_client.write_relationship(
            resource=ds_resource,
            relation=RelationType.KNOWLEDGE_GRAPH,
            subject=kg_resource,
        )
        await spicedb_client.write_relationship(
            resource=kg_resource,
            relation=RelationType.VIEWER,
            subject=user_subject,
        )

        has_view = await spicedb_client.check_permission(
            resource=ds_resource,
            permission=Permission.VIEW,
            subject=user_subject,
        )
        has_edit = await spicedb_client.check_permission(
            resource=ds_resource,
            permission=Permission.EDIT,
            subject=user_subject,
        )

        assert has_view is True, "Direct KG viewer should have VIEW on data source"
        assert has_edit is False, "Direct KG viewer should NOT have EDIT on data source"
