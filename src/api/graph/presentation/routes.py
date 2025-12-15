"""HTTP routes for Graph bounded context.

Provides REST API for manual testing and future external integrations.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from graph.infrastructure.protocols import NodeNeighborsResult
from graph.application.services import GraphMutationService, GraphQueryService
from graph.domain.value_objects import MutationOperation, MutationResult

router = APIRouter(prefix="/graph", tags=["graph"])


# Dependency injection placeholders
# These will be overridden in main.py or in tests
def get_query_service(
    data_source_id: str = Query(...),
) -> GraphQueryService:
    """Get GraphQueryService instance.

    This is a placeholder that will be overridden by dependency injection
    in main.py.
    """
    raise NotImplementedError(
        "GraphQueryService dependency not configured. "
        "This should be overridden in main.py."
    )


def get_mutation_service() -> GraphMutationService:
    """Get GraphMutationService instance.

    This is a placeholder that will be overridden by dependency injection
    in main.py.
    """
    raise NotImplementedError(
        "GraphMutationService dependency not configured. "
        "This should be overridden in main.py."
    )


@router.post("/mutations", status_code=status.HTTP_200_OK)
async def apply_mutations(
    operations: list[MutationOperation],
    service: GraphMutationService = Depends(get_mutation_service),
) -> MutationResult:
    """Apply a batch of mutation operations.

    Request body should be a JSON array of mutation operations.

    Example:
        [
            {
                "op": "CREATE",
                "type": "node",
                "id": "person:abc123def456789a",
                "label": "Person",
                "set_properties": {
                    "slug": "alice-smith",
                    "name": "Alice Smith",
                    "data_source_id": "ds-456",
                    "source_path": "people/alice.md"
                }
            }
        ]

    Returns:
        MutationResult with success status and operation count.

    Raises:
        HTTPException: 500 if mutation application fails.
    """
    result = service.apply_mutations(operations)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errors": result.errors},
        )

    return result


@router.get("/nodes/by-path")
async def find_by_path(
    path: str,
    service: GraphQueryService = Depends(get_query_service),
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
    service: GraphQueryService = Depends(get_query_service),
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
    service: GraphQueryService = Depends(get_query_service),
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
