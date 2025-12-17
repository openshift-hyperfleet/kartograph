"""HTTP routes for Graph bounded context.

Provides REST API for manual testing and future external integrations.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

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
from graph.domain.value_objects import MutationResult

router = APIRouter(prefix="/graph", tags=["graph"])


@router.post("/mutations", status_code=status.HTTP_200_OK)
async def apply_mutations(
    request: Request,
    service: GraphMutationService = Depends(get_graph_mutation_service),
) -> MutationResult:
    """Apply a batch of mutation operations from JSONL format.

    Request body should be JSONL (newline-delimited JSON), one operation per line.
    Content-Type: application/x-ndjson

    Example:
        {"op": "CREATE", "type": "node", "id": "person:abc123def456789a", "label": "Person", "set_properties": {"slug": "alice-smith", "name": "Alice Smith", "data_source_id": "ds-456", "source_path": "people/alice.md"}}
        {"op": "CREATE", "type": "node", "id": "person:def456abc123789a", "label": "Person", "set_properties": {"slug": "bob-jones", "name": "Bob Jones", "data_source_id": "ds-456", "source_path": "people/bob.md"}}

    Returns:
        MutationResult with success status and operation count.

        On validation error, returns success=false with detailed error messages
        in the errors array (HTTP 500).

    Raises:
        HTTPException: 500 if mutation application fails.
    """
    # Read raw body as string
    jsonl_content = await request.body()
    jsonl_str = jsonl_content.decode("utf-8")

    result = service.apply_mutations_from_jsonl(jsonl_str)

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
        node_type: Optional type filter (e.g., "Person")

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


@router.get("/ontology")
async def get_ontology(
    service: GraphSchemaService = Depends(get_schema_service),
) -> list[dict[str, Any]]:
    """Get graph ontology (type definitions).

    Returns all node and edge type definitions that have been created
    via DEFINE operations.

    Returns:
        List of type definitions with schema information
    """
    definitions = service.get_ontology()
    return [d.model_dump() for d in definitions]
