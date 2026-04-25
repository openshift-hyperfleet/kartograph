"""HTTP routes for Graph bounded context.

Provides REST API for manual testing and future external integrations.
"""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, status
from starlette.concurrency import run_in_threadpool

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from infrastructure.authorization_dependencies import get_spicedb_client
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)

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

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/graph",
    tags=["graph"],
    dependencies=[Depends(get_current_user)],
)


def _build_mutation_error_response(result: MutationResult) -> HTTPException:
    """Build the appropriate HTTPException for a failed mutation result.

    Uses the explicit ``error_kind`` field on MutationResult to select the
    HTTP status code:
    - "validation" → 422 Unprocessable Entity (bad input, parse errors, schema violations)
    - "server" or None → 500 Internal Server Error (infrastructure/database failures)

    For server errors, the actual error details are logged for observability but
    NOT exposed in the response body to prevent internal information leakage.
    """
    if result.error_kind == "validation":
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": result.errors},
        )
    # Log the actual error details for observability; return a generic payload
    # to avoid leaking infrastructure or database error details to clients.
    logger.error(
        "graph_mutation_server_error",
        errors=result.errors,
        error_kind=result.error_kind,
    )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"errors": ["internal server error"]},
    )


@router.post(
    "/knowledge-graphs/{knowledge_graph_id}/mutations",
    status_code=status.HTTP_200_OK,
)
async def apply_kg_mutations(
    knowledge_graph_id: str,
    jsonl_content: Annotated[
        str,
        Body(media_type="application/jsonlines"),
    ],
    service: Annotated[GraphMutationService, Depends(get_graph_mutation_service)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> MutationResult:
    """Apply mutation operations scoped to a specific KnowledgeGraph.

    This is the primary write endpoint for the Graph bounded context.
    It enforces:
    - **Authorization**: The caller must have ``edit`` permission on the target
      KnowledgeGraph (verified via SpiceDB).
    - **knowledge_graph_id stamping**: The system stamps ``knowledge_graph_id``
      on all CREATE and UPDATE operations, overwriting any caller-supplied value.
      This prevents callers from writing to a different graph than authorized.
    - **Tenant isolation**: Mutations execute against the tenant-specific AGE graph
      (``tenant_{tenant_id}``).

    Request body should be JSONL (newline-delimited JSON), one operation per line.
    Content-Type: application/jsonlines

    Args:
        knowledge_graph_id: ID of the target KnowledgeGraph (path parameter).
        jsonl_content: JSONL mutation log.
        service: Graph mutation service.
        authz: Authorization provider for SpiceDB permission checks.
        current_user: The authenticated user (provides user_id and tenant_id).

    Returns:
        MutationResult with success status and operation count.

    Raises:
        HTTPException: 403 Forbidden if the user lacks ``edit`` permission.
        HTTPException: 422 Unprocessable Entity for validation errors.
        HTTPException: 500 for database/execution errors.
    """
    # Enforce edit permission on the target KnowledgeGraph via SpiceDB
    subject = format_subject(ResourceType.USER, current_user.user_id.value)
    resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, knowledge_graph_id)
    has_edit = await authz.check_permission(resource, Permission.EDIT, subject)
    if not has_edit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"You do not have edit permission on knowledge graph '{knowledge_graph_id}'"
            ),
        )

    # Apply mutations — service stamps knowledge_graph_id on all CREATE/UPDATE ops
    result = await run_in_threadpool(
        service.apply_mutations_from_jsonl,
        jsonl_content=jsonl_content,
        knowledge_graph_id=knowledge_graph_id,
    )

    if not result.success:
        raise _build_mutation_error_response(result)

    return result


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
    nodes = await run_in_threadpool(service.search_by_slug, slug, node_type=node_type)
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
    response = await run_in_threadpool(service.get_neighbors, node_id)

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
    labels = await run_in_threadpool(
        service.get_node_labels, search=search, has_property=has_property
    )
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
    labels = await run_in_threadpool(service.get_edge_labels, search=search)
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
    schema = await run_in_threadpool(service.get_node_schema, label)

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
    schema = await run_in_threadpool(service.get_edge_schema, label)

    if schema is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Edge type '{label}' not found",
        )

    return schema
