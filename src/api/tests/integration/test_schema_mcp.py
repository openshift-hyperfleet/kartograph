"""Integration tests for MCP schema resources.

Tests the full stack from MCP resources through MCPSchemaService and
GraphSchemaService to the in-memory type definition repository.

Run with: pytest -m integration tests/integration/test_schema_mcp.py
"""

import json
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastmcp.client import Client

from graph.domain.value_objects import EntityType, TypeDefinition
from graph.infrastructure.type_definition_repository import (
    InMemoryTypeDefinitionRepository,
)
from query.presentation.mcp import mcp


pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def mcp_client_with_schema():
    """Create MCP client with schema service initialized."""
    # Set up type definition repository with test data
    repo = InMemoryTypeDefinitionRepository()

    # Add person node type
    person_def = TypeDefinition(
        label="person",
        entity_type=EntityType.NODE,
        description="A person entity",
        example_file_path="people/alice.md",
        example_in_file_path="name: Alice Smith",
        required_properties={"name"},
        optional_properties={"email", "role"},
    )
    repo.save(person_def)

    # Add project node type
    project_def = TypeDefinition(
        label="project",
        entity_type=EntityType.NODE,
        description="A software project",
        example_file_path="projects/kartograph.md",
        example_in_file_path="name: Kartograph",
        required_properties={"name"},
        optional_properties={"description", "url"},
    )
    repo.save(project_def)

    # Add knows edge type
    knows_def = TypeDefinition(
        label="knows",
        entity_type=EntityType.EDGE,
        description="Professional relationship",
        example_file_path="people/alice.md",
        example_in_file_path="colleagues: [@bob](bob.md)",
        required_properties={"since"},
        optional_properties=set(),
    )
    repo.save(knows_def)

    # Patch get_type_definition_repository to return our test repo
    with patch("graph.dependencies.get_type_definition_repository", return_value=repo):
        # Create and yield client
        async with Client(transport=mcp) as client:
            yield client


@pytest.mark.asyncio
async def test_ontology_resource_returns_all_type_definitions(mcp_client_with_schema):
    """Should return all type definitions."""
    # Get the ontology resource
    resources = await mcp_client_with_schema.list_resources()

    # Find schema://ontology resource
    ontology_resource = next(
        (r for r in resources if str(r.uri) == "schema://ontology"), None
    )
    assert ontology_resource is not None

    # Read the resource
    result = await mcp_client_with_schema.read_resource(uri="schema://ontology")

    # Parse JSON response  - result is a list
    data = json.loads(result[0].text)

    assert "type_definitions" in data
    assert "count" in data
    assert data["count"] == 3

    # Verify all three types are present
    labels = [td["label"] for td in data["type_definitions"]]
    assert "person" in labels
    assert "project" in labels
    assert "knows" in labels


@pytest.mark.asyncio
async def test_ontology_resource_includes_complete_type_information(
    mcp_client_with_schema,
):
    """Should include all type definition fields."""
    result = await mcp_client_with_schema.read_resource(uri="schema://ontology")

    data = json.loads(result[0].text)
    person_def = next(td for td in data["type_definitions"] if td["label"] == "person")

    assert person_def["entity_type"] == "node"
    assert person_def["description"] == "A person entity"
    assert person_def["example_file_path"] == "people/alice.md"
    assert person_def["example_in_file_path"] == "name: Alice Smith"
    assert "name" in person_def["required_properties"]
    assert "email" in person_def["optional_properties"]


@pytest.mark.asyncio
async def test_node_labels_resource_returns_node_labels(mcp_client_with_schema):
    """Should return all node type labels."""
    result = await mcp_client_with_schema.read_resource(uri="schema://nodes/labels")

    data = json.loads(result[0].text)

    assert "labels" in data
    assert "count" in data
    assert data["count"] == 2
    assert "person" in data["labels"]
    assert "project" in data["labels"]
    assert "knows" not in data["labels"]  # Edge type should not be included


@pytest.mark.asyncio
async def test_edge_labels_resource_returns_edge_labels(mcp_client_with_schema):
    """Should return all edge type labels."""
    result = await mcp_client_with_schema.read_resource(uri="schema://edges/labels")

    data = json.loads(result[0].text)

    assert "labels" in data
    assert "count" in data
    assert data["count"] == 1
    assert "knows" in data["labels"]
    assert "person" not in data["labels"]  # Node type should not be included


@pytest.mark.asyncio
async def test_node_schema_resource_returns_schema_by_label(mcp_client_with_schema):
    """Should return schema for specific node type."""
    result = await mcp_client_with_schema.read_resource(uri="schema://nodes/person")

    data = json.loads(result[0].text)

    assert data["label"] == "person"
    assert data["entity_type"] == "node"
    assert data["description"] == "A person entity"
    assert "name" in data["required_properties"]
    assert "email" in data["optional_properties"]


@pytest.mark.asyncio
async def test_node_schema_resource_returns_error_for_nonexistent(
    mcp_client_with_schema,
):
    """Should return error when node type not found."""
    result = await mcp_client_with_schema.read_resource(
        uri="schema://nodes/nonexistent"
    )

    data = json.loads(result[0].text)

    assert "error" in data
    assert "nonexistent" in data["error"]


@pytest.mark.asyncio
async def test_edge_schema_resource_returns_schema_by_label(mcp_client_with_schema):
    """Should return schema for specific edge type."""
    result = await mcp_client_with_schema.read_resource(uri="schema://edges/knows")

    data = json.loads(result[0].text)

    assert data["label"] == "knows"
    assert data["entity_type"] == "edge"
    assert data["description"] == "Professional relationship"
    assert "since" in data["required_properties"]


@pytest.mark.asyncio
async def test_edge_schema_resource_returns_error_for_nonexistent(
    mcp_client_with_schema,
):
    """Should return error when edge type not found."""
    result = await mcp_client_with_schema.read_resource(
        uri="schema://edges/nonexistent"
    )

    data = json.loads(result[0].text)

    assert "error" in data
    assert "nonexistent" in data["error"]


@pytest.mark.asyncio
async def test_resource_listing_includes_schema_resources(mcp_client_with_schema):
    """Should list all available schema resources."""
    resources = await mcp_client_with_schema.list_resources()

    resource_uris = [str(r.uri) for r in resources]

    # Static resources
    assert "schema://ontology" in resource_uris
    assert "schema://nodes/labels" in resource_uris
    assert "schema://edges/labels" in resource_uris

    # Dynamic resources (templates)
    schema_resources = [r for r in resources if str(r.uri).startswith("schema://")]
    assert len(schema_resources) >= 3
