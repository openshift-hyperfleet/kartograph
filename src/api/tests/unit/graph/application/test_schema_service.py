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
                label="person",
                entity_type=EntityType.NODE,
                description="A person entity",
                example_file_path="people/alice.md",
                example_in_file_path="Alice Smith is...",
                required_properties=["slug", "name"],
            ),
            TypeDefinition(
                label="knows",
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
                label="person",
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


class TestGetNodeLabels:
    """Tests for get_node_labels method."""

    def test_returns_all_node_labels(self, service, mock_repository):
        """Should return list of all node type labels."""
        type_defs = [
            TypeDefinition(
                label="person",
                entity_type=EntityType.NODE,
                description="A person",
                example_file_path="test.md",
                example_in_file_path="test",
                required_properties=["slug"],
            ),
            TypeDefinition(
                label="repository",
                entity_type=EntityType.NODE,
                description="A code repository",
                example_file_path="test.md",
                example_in_file_path="test",
                required_properties=["slug"],
            ),
            TypeDefinition(
                label="knows",
                entity_type=EntityType.EDGE,
                description="An edge",
                example_file_path="test.md",
                example_in_file_path="test",
                required_properties=[],
            ),
        ]
        mock_repository.get_all.return_value = type_defs

        result = service.get_node_labels()

        assert result == ["person", "repository"]
        assert "knows" not in result

    def test_filters_by_search_term(self, service, mock_repository):
        """Should filter labels by search term (case-insensitive)."""
        type_defs = [
            TypeDefinition(
                label="person",
                entity_type=EntityType.NODE,
                description="A person",
                example_file_path="test.md",
                example_in_file_path="test",
                required_properties=[],
            ),
            TypeDefinition(
                label="repository",
                entity_type=EntityType.NODE,
                description="A repo",
                example_file_path="test.md",
                example_in_file_path="test",
                required_properties=[],
            ),
        ]
        mock_repository.get_all.return_value = type_defs

        result = service.get_node_labels(search="repo")

        assert result == ["repository"]
        assert "person" not in result

    def test_filters_by_has_property(self, service, mock_repository):
        """Should filter by presence of property."""
        type_defs = [
            TypeDefinition(
                label="person",
                entity_type=EntityType.NODE,
                description="A person",
                example_file_path="test.md",
                example_in_file_path="test",
                required_properties=["slug"],
                optional_properties=["email", "age"],
            ),
            TypeDefinition(
                label="repository",
                entity_type=EntityType.NODE,
                description="A repo",
                example_file_path="test.md",
                example_in_file_path="test",
                required_properties=["slug"],
                optional_properties=["url"],
            ),
        ]
        mock_repository.get_all.return_value = type_defs

        result = service.get_node_labels(has_property="email")

        assert result == ["person"]
        assert "repository" not in result


class TestGetEdgeLabels:
    """Tests for get_edge_labels method."""

    def test_returns_all_edge_labels(self, service, mock_repository):
        """Should return list of all edge type labels."""
        type_defs = [
            TypeDefinition(
                label="person",
                entity_type=EntityType.NODE,
                description="A person",
                example_file_path="test.md",
                example_in_file_path="test",
                required_properties=[],
            ),
            TypeDefinition(
                label="knows",
                entity_type=EntityType.EDGE,
                description="Knows relationship",
                example_file_path="test.md",
                example_in_file_path="test",
                required_properties=[],
            ),
            TypeDefinition(
                label="owns",
                entity_type=EntityType.EDGE,
                description="Owns relationship",
                example_file_path="test.md",
                example_in_file_path="test",
                required_properties=[],
            ),
        ]
        mock_repository.get_all.return_value = type_defs

        result = service.get_edge_labels()

        assert result == ["knows", "owns"]
        assert "person" not in result


class TestGetNodeSchema:
    """Tests for get_node_schema method."""

    def test_returns_node_schema(self, service, mock_repository):
        """Should return full TypeDefinition for node label."""
        type_def = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            example_file_path="test.md",
            example_in_file_path="test",
            required_properties=["slug", "name"],
            optional_properties=["email"],
        )
        mock_repository.get.return_value = type_def

        result = service.get_node_schema("person")

        assert result == type_def
        mock_repository.get.assert_called_once_with("person", "node")

    def test_returns_none_when_not_found(self, service, mock_repository):
        """Should return None when label doesn't exist."""
        mock_repository.get.return_value = None

        result = service.get_node_schema("NonExistent")

        assert result is None


class TestGetEdgeSchema:
    """Tests for get_edge_schema method."""

    def test_returns_edge_schema(self, service, mock_repository):
        """Should return full TypeDefinition for edge label."""
        type_def = TypeDefinition(
            label="knows",
            entity_type=EntityType.EDGE,
            description="Knows relationship",
            example_file_path="test.md",
            example_in_file_path="test",
            required_properties=[],
        )
        mock_repository.get.return_value = type_def

        result = service.get_edge_schema("knows")

        assert result == type_def
        mock_repository.get.assert_called_once_with("knows", "edge")
