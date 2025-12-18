"""HTTP routes for Graph bounded context.

Provides REST API for manual testing and future external integrations.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status

from graph.ports.protocols import NodeNeighborsResult
from graph.application.services import (
    GraphMutationService,
    GraphQueryService,
    GraphSchemaService,
)
from graph.dependencies import (
    get_graph_mutation_service,
    get_graph_query_service,
    get_schema_service,
)
from graph.domain.value_objects import (
    MutationResult,
    SchemaLabelsResponse,
    TypeDefinition,
)

router = APIRouter(prefix="/graph", tags=["graph"])


@router.post("/mutations", status_code=status.HTTP_200_OK)
async def apply_mutations(
    jsonl_content: str = Body(
        ...,
        media_type="application/jsonlines",
    ),
    service: GraphMutationService = Depends(get_graph_mutation_service),
) -> MutationResult:
    """Apply a batch of mutation operations from JSONL format.

    Request body should be JSONL (newline-delimited JSON), one operation per line.
    Content-Type: application/x-ndjson

    Example:


    ```jsonl
    {"op": "CREATE", "type": "node", "id": "person:1a2b3c4d5e6f7890", "label": "person", "set_properties": {"slug": "alice-smith", "name": "Alice Smith", "data_source_id": "ds-123", "source_path": "people/alice.md"}}
    {"op": "CREATE", "type": "node", "id": "person:abcdef0123456789", "label": "person", "set_properties": {"slug": "bob-jones", "name": "Bob Jones", "data_source_id": "ds-123", "source_path": "people/bob.md"}}
    {"op": "CREATE", "type": "edge", "id": "knows:9f8e7d6c5b4a3210", "label": "knows", "start_id": "person:1a2b3c4d5e6f7890", "end_id": "person:abcdef0123456789", "set_properties": {"since": 2020, "data_source_id": "ds-123", "source_path": "people/alice.md"}}
    {"op": "DEFINE","type": "node","label": "person","description": "A person entity representing an individual contributor, maintainer, or team member. Extracted from MAINTAINERS.md, git commit authors, @-mentions in pull requests, and people/ directory markdown files.","example_file_path": "people/alice-smith.md","example_in_file_path": "name: Alice Smith email: alice@example.com github: asmith role: Senior Engineer # Alice Smith Alice is a senior engineer focusing on backend systems.","required_properties": ["name"]}
    {"op": "DEFINE","type": "edge","label": "knows","description": "Represents a professional relationship or acquaintance between two people, typically colleagues or collaborators. Extracted from co-authorship on pull requests, shared repository maintainership, or explicit mentions in people profiles.","example_file_path": "people/alice-smith.md","example_in_file_path": "## Colleagues - [@bob-jones](../people/bob-jones.md) - worked together since 2020 - [@charlie-wilson](../people/charlie-wilson.md) - collaborated on Project X","required_properties": ["since"]}
    {"op": "CREATE","type": "node","id": "person:1a2b3c4d5e6f7890","label": "person","set_properties": {"slug": "alice-smith","name": "Alice Smith","data_source_id": "ds-123","source_path": "people/alice.md"}}
    {"op": "CREATE","type": "node","id": "person:abcdef0123456789","label": "person","set_properties": {"slug": "bob-jones","name": "Bob Jones","data_source_id": "ds-123","source_path": "people/bob.md"}}
    {"op": "CREATE","type": "edge","id": "knows:9f8e7d6c5b4a3210","label": "knows","start_id": "person:1a2b3c4d5e6f7890","end_id": "person:abcdef0123456789","set_properties": {"since": "2020","data_source_id": "ds-123","source_path": "people/alice.md"}}
    ```


    Returns:
        MutationResult with success status and operation count.

        On validation error, returns success=false with detailed error messages
        in the errors array (HTTP 500).

    Raises:
        HTTPException: 500 if mutation application fails.
    """

    result = service.apply_mutations_from_jsonl(jsonl_content=jsonl_content)

    if not result.success:
        # Check if it's a validation error vs execution error
        # Validation errors contain specific keywords
        is_validation_error = False
        if result.errors:
            error_text = " ".join(result.errors).lower()
            validation_keywords = [
                "json",
                "parse",
                "validation",
                "required",
                "missing",
                "invalid",
            ]
            is_validation_error = any(
                keyword in error_text for keyword in validation_keywords
            )

        if is_validation_error:
            # Validation error - return 422
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"errors": result.errors},
            )
        else:
            # Database/execution error - return 500
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"errors": result.errors},
            )

    return result


@router.get("/nodes/by-path")
async def find_by_path(
    path: str,
    service: GraphQueryService = Depends(get_graph_query_service),
) -> dict[str, Any]:
    """Find nodes and edges by source file path.

    Query parameter:
        path: Source file path (e.g., "people/alice.md")

    Returns:
        {
            "nodes": [...],
            "edges": [...]
        }
    """
    nodes, edges = service.get_nodes_by_path(path)
    return {
        "nodes": [n.model_dump() for n in nodes],
        "edges": [e.model_dump() for e in edges],
    }


@router.get("/nodes/by-slug")
async def find_by_slug(
    slug: str,
    node_type: str | None = None,
    service: GraphQueryService = Depends(get_graph_query_service),
) -> dict[str, Any]:
    """Find nodes by slug.

    Query parameters:
        slug: Entity slug (e.g., "alice-smith")
        node_type: Optional type filter (e.g., "person")

    Returns:
        {
            "nodes": [...]
        }
    """
    nodes = service.search_by_slug(slug, node_type=node_type)
    return {"nodes": [n.model_dump() for n in nodes]}


@router.get("/nodes/{node_id}/neighbors")
async def get_neighbors(
    node_id: str,
    service: GraphQueryService = Depends(get_graph_query_service),
) -> NodeNeighborsResult:
    """Get neighboring nodes and connecting edges.

    Path parameter:
        node_id: The node ID to find neighbors for

    Returns:
        {
            "nodes": [...],
            "edges": [...]
        }
    """
    response = service.get_neighbors(node_id)

    return response


@router.get("/schema/nodes", response_model=SchemaLabelsResponse)
async def get_node_labels_endpoint(
    search: str | None = None,
    has_property: str | None = None,
    service: GraphSchemaService = Depends(get_schema_service),
) -> SchemaLabelsResponse:
    """Get list of node type labels.

    Query parameters:
        search: Optional search term to filter labels (case-insensitive)
        has_property: Optional property name filter

    Returns:
        SchemaLabelsResponse with labels and count
    """
    labels = service.get_node_labels(search=search, has_property=has_property)
    return SchemaLabelsResponse(labels=labels, count=len(labels))


@router.get("/schema/edges", response_model=SchemaLabelsResponse)
async def get_edge_labels_endpoint(
    search: str | None = None,
    service: GraphSchemaService = Depends(get_schema_service),
) -> SchemaLabelsResponse:
    """Get list of edge type labels.

    Query parameters:
        search: Optional search term to filter labels (case-insensitive)

    Returns:
        SchemaLabelsResponse with labels and count
    """
    labels = service.get_edge_labels(search=search)
    return SchemaLabelsResponse(labels=labels, count=len(labels))


@router.get("/schema/nodes/{label}", response_model=TypeDefinition)
async def get_node_schema_endpoint(
    label: str,
    service: GraphSchemaService = Depends(get_schema_service),
) -> TypeDefinition:
    """Get full schema for a specific node type.

    Path parameter:
        label: The node type label (e.g., "person")

    Returns:
        Full TypeDefinition including required/optional properties

    Raises:
        HTTPException: 404 if label not found
    """
    schema = service.get_node_schema(label)

    if schema is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node type '{label}' not found",
        )

    return schema


@router.get("/schema/edges/{label}", response_model=TypeDefinition)
async def get_edge_schema_endpoint(
    label: str,
    service: GraphSchemaService = Depends(get_schema_service),
) -> TypeDefinition:
    """Get full schema for a specific edge type.

    Path parameter:
        label: The edge type label (e.g., "knows")

    Returns:
        Full TypeDefinition including required/optional properties

    Raises:
        HTTPException: 404 if label not found
    """
    schema = service.get_edge_schema(label)

    if schema is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Edge type '{label}' not found",
        )

    return schema
