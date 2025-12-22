"""Unit tests for infrastructure MCP composition layer."""

from unittest.mock import patch

from graph.application.services import GraphSchemaService
from infrastructure.mcp_dependencies import get_schema_service_for_mcp


class TestGetSchemaServiceForMCP:
    """Tests for get_schema_service_for_mcp composition function."""

    @patch("graph.dependencies.get_type_definition_repository")
    def test_returns_graph_schema_service(self, mock_get_repo):
        """Should return GraphSchemaService instance."""
        result = get_schema_service_for_mcp()

        assert isinstance(result, GraphSchemaService)
        mock_get_repo.assert_called_once()

    @patch("graph.dependencies.get_type_definition_repository")
    def test_injects_type_definition_repository(self, mock_get_repo):
        """Should inject type definition repository."""
        from graph.infrastructure.type_definition_repository import (
            InMemoryTypeDefinitionRepository,
        )

        mock_repo = InMemoryTypeDefinitionRepository()
        mock_get_repo.return_value = mock_repo

        result = get_schema_service_for_mcp()

        assert result._type_definition_repository is mock_repo
