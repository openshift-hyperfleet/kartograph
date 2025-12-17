"""Unit tests for GraphSchemaService."""

from unittest.mock import create_autospec

import pytest

from graph.application.observability.schema_service_probe import SchemaServiceProbe
from graph.application.services.graph_schema_service import GraphSchemaService
from graph.domain.value_objects import EntityType, TypeDefinition
from graph.ports.repositories import ITypeDefinitionRepository


@pytest.fixture
def mock_repository():
    """Create mock type definition repository."""
    return create_autospec(ITypeDefinitionRepository, instance=True)


@pytest.fixture
def mock_probe():
    """Create mock probe."""
    return create_autospec(SchemaServiceProbe, instance=True)


@pytest.fixture
def service(mock_repository, mock_probe):
    """Create service with mock dependencies."""
    return GraphSchemaService(
        type_definition_repository=mock_repository,
        probe=mock_probe,
    )


class TestGraphSchemaServiceInit:
    """Tests for service initialization."""

    def test_stores_repository(self, mock_repository):
        """Service should store repository reference."""
        service = GraphSchemaService(type_definition_repository=mock_repository)
        assert service._type_definition_repository is mock_repository

    def test_uses_default_probe_when_not_provided(self, mock_repository):
        """Should create default probe when not provided."""
        service = GraphSchemaService(type_definition_repository=mock_repository)
        assert service._probe is not None


class TestGetOntology:
    """Tests for get_ontology method."""

    def test_delegates_to_repository(self, service, mock_repository):
        """Should delegate to repository.get_all()."""
        mock_repository.get_all.return_value = []

        service.get_ontology()

        mock_repository.get_all.assert_called_once()

    def test_returns_type_definitions(self, service, mock_repository):
        """Should return list of TypeDefinitions."""
        type_defs = [
            TypeDefinition(
                label="Person",
                entity_type=EntityType.NODE,
                description="A person entity",
                example_file_path="people/alice.md",
                example_in_file_path="Alice Smith is...",
                required_properties=["slug", "name"],
            ),
            TypeDefinition(
                label="KNOWS",
                entity_type=EntityType.EDGE,
                description="Person knows another person",
                example_file_path="people/alice.md",
                example_in_file_path="Alice knows Bob",
                required_properties=[],
            ),
        ]
        mock_repository.get_all.return_value = type_defs

        result = service.get_ontology()

        assert result == type_defs
        assert len(result) == 2

    def test_records_observation(self, service, mock_repository, mock_probe):
        """Should record observation when ontology retrieved."""
        type_defs = [
            TypeDefinition(
                label="Person",
                entity_type=EntityType.NODE,
                description="test",
                example_file_path="test.md",
                example_in_file_path="test content",
                required_properties=[],
            )
        ]
        mock_repository.get_all.return_value = type_defs

        service.get_ontology()

        mock_probe.ontology_retrieved.assert_called_once()
        call_args = mock_probe.ontology_retrieved.call_args
        assert call_args.kwargs["count"] == 1

    def test_returns_empty_list_when_no_definitions(self, service, mock_repository):
        """Should return empty list when no type definitions exist."""
        mock_repository.get_all.return_value = []

        result = service.get_ontology()

        assert result == []
