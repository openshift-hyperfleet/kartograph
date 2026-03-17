"""Unit tests for ManagementEventTranslator (TDD - tests first).

These tests verify that Management domain events are correctly translated into
SpiceDB relationship operations using type-safe enums.

SpiceDB schema under test:

    definition knowledge_graph {
        relation workspace: workspace
        relation tenant: tenant
        relation admin: user | group#member
        relation editor: user | group#member
        relation viewer: user | group#member
        ...
    }

    definition data_source {
        relation knowledge_graph: knowledge_graph
        relation tenant: tenant
        ...
    }
"""

import pytest

from management.infrastructure.outbox import ManagementEventTranslator
from shared_kernel.authorization.types import RelationType, ResourceType
from shared_kernel.outbox.operations import (
    DeleteRelationship,
    DeleteRelationshipsByFilter,
    WriteRelationship,
)


class TestManagementEventTranslatorSupportedEvents:
    """Tests for supported event types."""

    def test_supports_all_management_domain_events(self):
        """Translator should support all Management domain event types."""
        translator = ManagementEventTranslator()
        supported = translator.supported_event_types()

        assert "KnowledgeGraphCreated" in supported
        assert "KnowledgeGraphUpdated" in supported
        assert "KnowledgeGraphDeleted" in supported
        assert "DataSourceCreated" in supported
        assert "DataSourceUpdated" in supported
        assert "DataSourceDeleted" in supported
        assert "DataSourceSyncRequested" in supported

    def test_supports_exactly_seven_event_types(self):
        """Translator should support exactly 7 event types."""
        translator = ManagementEventTranslator()
        supported = translator.supported_event_types()

        assert len(supported) == 7


class TestManagementEventTranslatorKnowledgeGraphCreated:
    """Tests for KnowledgeGraphCreated translation.

    SpiceDB relationships created:
    - knowledge_graph:<kg_id>#workspace@workspace:<workspace_id>
    - knowledge_graph:<kg_id>#tenant@tenant:<tenant_id>
    """

    def test_translates_to_workspace_and_tenant_relationships(self):
        """KnowledgeGraphCreated should produce workspace and tenant writes."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "workspace_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "name": "My Knowledge Graph",
            "description": "A test knowledge graph",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "created_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("KnowledgeGraphCreated", payload)

        assert len(operations) == 2
        assert all(isinstance(op, WriteRelationship) for op in operations)

    def test_first_operation_is_workspace_relationship(self):
        """First operation should write knowledge_graph#workspace@workspace."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "workspace_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "name": "My Knowledge Graph",
            "description": "A test knowledge graph",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "created_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("KnowledgeGraphCreated", payload)

        workspace_op = operations[0]
        assert isinstance(workspace_op, WriteRelationship)
        assert workspace_op.resource_type == ResourceType.KNOWLEDGE_GRAPH
        assert workspace_op.resource_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert workspace_op.relation == RelationType.WORKSPACE
        assert workspace_op.subject_type == ResourceType.WORKSPACE
        assert workspace_op.subject_id == "01ARZCX0P0HZGQP3MZXQQ0NNXX"

    def test_second_operation_is_tenant_relationship(self):
        """Second operation should write knowledge_graph#tenant@tenant."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "workspace_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "name": "My Knowledge Graph",
            "description": "A test knowledge graph",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "created_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("KnowledgeGraphCreated", payload)

        tenant_op = operations[1]
        assert isinstance(tenant_op, WriteRelationship)
        assert tenant_op.resource_type == ResourceType.KNOWLEDGE_GRAPH
        assert tenant_op.resource_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert tenant_op.relation == RelationType.TENANT
        assert tenant_op.subject_type == ResourceType.TENANT
        assert tenant_op.subject_id == "01ARZCX0P0HZGQP3MZXQQ0NNYY"

    def test_formatted_resource_and_subject_strings(self):
        """Operations should format resource and subject as type:id strings."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "workspace_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "name": "My Knowledge Graph",
            "description": "A test knowledge graph",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "created_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("KnowledgeGraphCreated", payload)

        assert operations[0].resource == "knowledge_graph:01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert operations[0].subject == "workspace:01ARZCX0P0HZGQP3MZXQQ0NNXX"
        assert operations[0].relation_name == "workspace"

        assert operations[1].resource == "knowledge_graph:01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert operations[1].subject == "tenant:01ARZCX0P0HZGQP3MZXQQ0NNYY"
        assert operations[1].relation_name == "tenant"


class TestManagementEventTranslatorKnowledgeGraphUpdated:
    """Tests for KnowledgeGraphUpdated translation.

    KnowledgeGraphUpdated is a no-op for SpiceDB — name/description
    changes do not affect authorization relationships.
    """

    def test_returns_empty_list(self):
        """KnowledgeGraphUpdated should produce no SpiceDB operations."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "name": "Updated Name",
            "description": "Updated description",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "updated_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("KnowledgeGraphUpdated", payload)

        assert operations == []

    def test_handler_is_registered(self):
        """KnowledgeGraphUpdated should be in supported event types."""
        translator = ManagementEventTranslator()
        assert "KnowledgeGraphUpdated" in translator.supported_event_types()


class TestManagementEventTranslatorKnowledgeGraphDeleted:
    """Tests for KnowledgeGraphDeleted translation.

    SpiceDB cleanup operations:
    1. DeleteRelationship: knowledge_graph:<kg_id>#workspace@workspace:<ws_id>
    2. DeleteRelationship: knowledge_graph:<kg_id>#tenant@tenant:<tenant_id>
    3. DeleteRelationshipsByFilter: knowledge_graph:<kg_id>#admin (any subject)
    4. DeleteRelationshipsByFilter: knowledge_graph:<kg_id>#editor (any subject)
    5. DeleteRelationshipsByFilter: knowledge_graph:<kg_id>#viewer (any subject)
    """

    def test_produces_five_operations(self):
        """KnowledgeGraphDeleted should produce 5 cleanup operations."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "workspace_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "deleted_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("KnowledgeGraphDeleted", payload)

        assert len(operations) == 5

    def test_first_operation_deletes_workspace_relationship(self):
        """First operation should delete knowledge_graph#workspace@workspace."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "workspace_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "deleted_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("KnowledgeGraphDeleted", payload)

        workspace_delete = operations[0]
        assert isinstance(workspace_delete, DeleteRelationship)
        assert workspace_delete.resource_type == ResourceType.KNOWLEDGE_GRAPH
        assert workspace_delete.resource_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert workspace_delete.relation == RelationType.WORKSPACE
        assert workspace_delete.subject_type == ResourceType.WORKSPACE
        assert workspace_delete.subject_id == "01ARZCX0P0HZGQP3MZXQQ0NNXX"

    def test_second_operation_deletes_tenant_relationship(self):
        """Second operation should delete knowledge_graph#tenant@tenant."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "workspace_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "deleted_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("KnowledgeGraphDeleted", payload)

        tenant_delete = operations[1]
        assert isinstance(tenant_delete, DeleteRelationship)
        assert tenant_delete.resource_type == ResourceType.KNOWLEDGE_GRAPH
        assert tenant_delete.resource_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert tenant_delete.relation == RelationType.TENANT
        assert tenant_delete.subject_type == ResourceType.TENANT
        assert tenant_delete.subject_id == "01ARZCX0P0HZGQP3MZXQQ0NNYY"

    def test_third_operation_filters_admin_grants(self):
        """Third operation should filter-delete all admin grants on the KG."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "workspace_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "deleted_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("KnowledgeGraphDeleted", payload)

        admin_filter = operations[2]
        assert isinstance(admin_filter, DeleteRelationshipsByFilter)
        assert admin_filter.resource_type == ResourceType.KNOWLEDGE_GRAPH
        assert admin_filter.resource_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert admin_filter.relation == RelationType.ADMIN

    def test_fourth_operation_filters_editor_grants(self):
        """Fourth operation should filter-delete all editor grants on the KG."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "workspace_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "deleted_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("KnowledgeGraphDeleted", payload)

        editor_filter = operations[3]
        assert isinstance(editor_filter, DeleteRelationshipsByFilter)
        assert editor_filter.resource_type == ResourceType.KNOWLEDGE_GRAPH
        assert editor_filter.resource_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert editor_filter.relation == RelationType.EDITOR

    def test_fifth_operation_filters_viewer_grants(self):
        """Fifth operation should filter-delete all viewer grants on the KG."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "workspace_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "deleted_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("KnowledgeGraphDeleted", payload)

        viewer_filter = operations[4]
        assert isinstance(viewer_filter, DeleteRelationshipsByFilter)
        assert viewer_filter.resource_type == ResourceType.KNOWLEDGE_GRAPH
        assert viewer_filter.resource_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert viewer_filter.relation == RelationType.VIEWER

    def test_order_is_direct_deletes_then_filter_deletes(self):
        """Direct relationship deletes should precede filter-based deletes."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "workspace_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "deleted_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("KnowledgeGraphDeleted", payload)

        # First two should be direct DeleteRelationship
        assert isinstance(operations[0], DeleteRelationship)
        assert isinstance(operations[1], DeleteRelationship)

        # Last three should be DeleteRelationshipsByFilter
        assert isinstance(operations[2], DeleteRelationshipsByFilter)
        assert isinstance(operations[3], DeleteRelationshipsByFilter)
        assert isinstance(operations[4], DeleteRelationshipsByFilter)

    def test_filter_deletes_have_no_subject_constraints(self):
        """Filter-based deletes should not specify subject type or ID.

        This ensures all grants are cleaned up regardless of whether
        the subject is a user or group#member.
        """
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "workspace_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "deleted_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("KnowledgeGraphDeleted", payload)

        for filter_op in operations[2:]:
            assert isinstance(filter_op, DeleteRelationshipsByFilter)
            assert filter_op.subject_type is None
            assert filter_op.subject_id is None


class TestManagementEventTranslatorDataSourceCreated:
    """Tests for DataSourceCreated translation.

    SpiceDB relationships created:
    - data_source:<ds_id>#knowledge_graph@knowledge_graph:<kg_id>
    - data_source:<ds_id>#tenant@tenant:<tenant_id>
    """

    def test_translates_to_knowledge_graph_and_tenant_relationships(self):
        """DataSourceCreated should produce knowledge_graph and tenant writes."""
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "name": "GitHub Adapter",
            "adapter_type": "github",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "created_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("DataSourceCreated", payload)

        assert len(operations) == 2
        assert all(isinstance(op, WriteRelationship) for op in operations)

    def test_first_operation_is_knowledge_graph_relationship(self):
        """First operation should write data_source#knowledge_graph@knowledge_graph."""
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "name": "GitHub Adapter",
            "adapter_type": "github",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "created_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("DataSourceCreated", payload)

        kg_op = operations[0]
        assert isinstance(kg_op, WriteRelationship)
        assert kg_op.resource_type == ResourceType.DATA_SOURCE
        assert kg_op.resource_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert kg_op.relation == RelationType.KNOWLEDGE_GRAPH
        assert kg_op.subject_type == ResourceType.KNOWLEDGE_GRAPH
        assert kg_op.subject_id == "01ARZCX0P0HZGQP3MZXQQ0NNYY"

    def test_second_operation_is_tenant_relationship(self):
        """Second operation should write data_source#tenant@tenant."""
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "name": "GitHub Adapter",
            "adapter_type": "github",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "created_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("DataSourceCreated", payload)

        tenant_op = operations[1]
        assert isinstance(tenant_op, WriteRelationship)
        assert tenant_op.resource_type == ResourceType.DATA_SOURCE
        assert tenant_op.resource_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert tenant_op.relation == RelationType.TENANT
        assert tenant_op.subject_type == ResourceType.TENANT
        assert tenant_op.subject_id == "01ARZCX0P0HZGQP3MZXQQ0NNXX"

    def test_formatted_resource_and_subject_strings(self):
        """Operations should format resource and subject as type:id strings."""
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "name": "GitHub Adapter",
            "adapter_type": "github",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "created_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("DataSourceCreated", payload)

        assert operations[0].resource == "data_source:01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert operations[0].subject == "knowledge_graph:01ARZCX0P0HZGQP3MZXQQ0NNYY"
        assert operations[0].relation_name == "knowledge_graph"

        assert operations[1].resource == "data_source:01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert operations[1].subject == "tenant:01ARZCX0P0HZGQP3MZXQQ0NNXX"
        assert operations[1].relation_name == "tenant"


class TestManagementEventTranslatorDataSourceUpdated:
    """Tests for DataSourceUpdated translation.

    DataSourceUpdated is a no-op for SpiceDB — connection configuration
    changes do not affect authorization relationships.
    """

    def test_returns_empty_list(self):
        """DataSourceUpdated should produce no SpiceDB operations."""
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "name": "Updated Adapter",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "updated_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("DataSourceUpdated", payload)

        assert operations == []

    def test_handler_is_registered(self):
        """DataSourceUpdated should be in supported event types."""
        translator = ManagementEventTranslator()
        assert "DataSourceUpdated" in translator.supported_event_types()


class TestManagementEventTranslatorDataSourceDeleted:
    """Tests for DataSourceDeleted translation.

    SpiceDB relationships deleted:
    - data_source:<ds_id>#knowledge_graph@knowledge_graph:<kg_id>
    - data_source:<ds_id>#tenant@tenant:<tenant_id>
    """

    def test_produces_two_delete_operations(self):
        """DataSourceDeleted should produce 2 delete operations."""
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "deleted_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("DataSourceDeleted", payload)

        assert len(operations) == 2
        assert all(isinstance(op, DeleteRelationship) for op in operations)

    def test_first_operation_deletes_knowledge_graph_relationship(self):
        """First operation should delete data_source#knowledge_graph@knowledge_graph."""
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "deleted_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("DataSourceDeleted", payload)

        kg_delete = operations[0]
        assert isinstance(kg_delete, DeleteRelationship)
        assert kg_delete.resource_type == ResourceType.DATA_SOURCE
        assert kg_delete.resource_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert kg_delete.relation == RelationType.KNOWLEDGE_GRAPH
        assert kg_delete.subject_type == ResourceType.KNOWLEDGE_GRAPH
        assert kg_delete.subject_id == "01ARZCX0P0HZGQP3MZXQQ0NNYY"

    def test_second_operation_deletes_tenant_relationship(self):
        """Second operation should delete data_source#tenant@tenant."""
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "deleted_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("DataSourceDeleted", payload)

        tenant_delete = operations[1]
        assert isinstance(tenant_delete, DeleteRelationship)
        assert tenant_delete.resource_type == ResourceType.DATA_SOURCE
        assert tenant_delete.resource_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert tenant_delete.relation == RelationType.TENANT
        assert tenant_delete.subject_type == ResourceType.TENANT
        assert tenant_delete.subject_id == "01ARZCX0P0HZGQP3MZXQQ0NNXX"

    def test_formatted_resource_and_subject_strings(self):
        """Delete operations should format resource and subject correctly."""
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "deleted_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("DataSourceDeleted", payload)

        assert operations[0].resource == "data_source:01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert operations[0].subject == "knowledge_graph:01ARZCX0P0HZGQP3MZXQQ0NNYY"
        assert operations[0].relation_name == "knowledge_graph"

        assert operations[1].resource == "data_source:01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert operations[1].subject == "tenant:01ARZCX0P0HZGQP3MZXQQ0NNXX"
        assert operations[1].relation_name == "tenant"


class TestManagementEventTranslatorDataSourceSyncRequested:
    """Tests for DataSourceSyncRequested translation.

    DataSourceSyncRequested is a no-op for SpiceDB — sync requests
    do not affect authorization relationships.
    """

    def test_returns_empty_list(self):
        """DataSourceSyncRequested should produce no SpiceDB operations."""
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "requested_by": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
        }

        operations = translator.translate("DataSourceSyncRequested", payload)

        assert operations == []

    def test_handler_is_registered(self):
        """DataSourceSyncRequested should be in supported event types."""
        translator = ManagementEventTranslator()
        assert "DataSourceSyncRequested" in translator.supported_event_types()


class TestManagementEventTranslatorValidation:
    """Tests for translator handler validation.

    The translator validates at initialization that every event in the
    DomainEvent union type has a corresponding handler method.
    """

    def test_translator_is_instantiable(self):
        """ManagementEventTranslator should instantiate without error.

        This implicitly verifies _validate_handlers passes — all 7
        domain events have registered handlers.
        """
        translator = ManagementEventTranslator()
        assert translator is not None

    def test_supported_event_types_returns_frozenset(self):
        """supported_event_types should return a frozenset."""
        translator = ManagementEventTranslator()
        supported = translator.supported_event_types()
        assert isinstance(supported, frozenset)

    def test_raises_value_error_for_unknown_event_type(self):
        """Translator should raise ValueError for unknown event types."""
        translator = ManagementEventTranslator()

        with pytest.raises(ValueError) as exc_info:
            translator.translate("UnknownEvent", {})

        assert "Unknown event type" in str(exc_info.value)


class TestManagementEventTranslatorErrors:
    """Tests for error handling."""

    def test_raises_on_unsupported_event_type(self):
        """Translator should raise ValueError for unknown event types."""
        translator = ManagementEventTranslator()

        with pytest.raises(ValueError) as exc_info:
            translator.translate("SomeRandomEvent", {})

        assert "Unknown event type" in str(exc_info.value)

    def test_raises_on_iam_event_type(self):
        """Translator should raise ValueError for IAM events (wrong context)."""
        translator = ManagementEventTranslator()

        with pytest.raises(ValueError):
            translator.translate("GroupCreated", {})

    def test_raises_on_empty_event_type(self):
        """Translator should raise ValueError for empty event type string."""
        translator = ManagementEventTranslator()

        with pytest.raises(ValueError):
            translator.translate("", {})
