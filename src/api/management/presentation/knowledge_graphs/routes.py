"""HTTP routes for Knowledge Graph management."""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)
from management.dependencies.knowledge_graph import get_knowledge_graph_service
from management.ports.exceptions import (
    DuplicateKnowledgeGraphNameError,
    KnowledgeGraphNotFoundError,
    UnauthorizedError,
)
from management.presentation.knowledge_graphs.models import (
    CreateKnowledgeGraphRequest,
    KnowledgeGraphListResponse,
    KnowledgeGraphResponse,
    OntologyConfigRequest,
    OntologyConfigResponse,
    UpdateKnowledgeGraphRequest,
)
from shared_kernel.authorization.types import Permission

router = APIRouter(tags=["knowledge-graphs"])


@router.get(
    "/knowledge-graphs",
    status_code=status.HTTP_200_OK,
)
async def list_knowledge_graphs(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
    permission: Annotated[
        Literal["view", "edit"],
        Query(
            description=(
                "Filter by the minimum permission the caller must have on each "
                "knowledge graph. Use 'edit' to show only KGs the user can submit "
                "mutations to (e.g. for the Mutations Console KG selector)."
            )
        ),
    ] = "view",
    workspace_id: Annotated[
        Optional[str],
        Query(
            description=(
                "Optional workspace ID. When provided, results are filtered to "
                "knowledge graphs in that workspace that the user has the requested "
                "permission on. Used by the Mutations Console KG selector to satisfy "
                "the 'within the current workspace' scoping clause."
            )
        ),
    ] = None,
) -> KnowledgeGraphListResponse:
    """List knowledge graphs accessible to the current user in their tenant.

    Returns knowledge graphs filtered by SpiceDB permission checks.

    - ``?permission=view`` (default): returns all KGs the user can read.
    - ``?permission=edit``: returns only KGs the user can mutate — used by the
      Mutations Console to populate the knowledge-graph selector.
    - ``?workspace_id=<id>``: further scopes results to a specific workspace.
      Does NOT require workspace-level VIEW permission — per-KG permission checks
      are sufficient. Used by the Mutations Console KG selector.
    - Without ``?workspace_id=``: returns all accessible KGs in the tenant
      (existing behaviour, no regression).

    Args:
        current_user: Current authenticated user with tenant context
        service: Knowledge graph service for orchestration
        permission: Minimum permission level to filter by (view or edit)
        workspace_id: Optional workspace to scope results to

    Returns:
        KnowledgeGraphListResponse with all accessible KGs

    Raises:
        HTTPException: 500 for unexpected errors
    """
    perm = Permission.EDIT if permission == "edit" else Permission.VIEW
    try:
        if workspace_id:
            kgs = await service.list_for_workspace_with_permission(
                user_id=current_user.user_id.value,
                workspace_id=workspace_id,
                permission=perm,
            )
        else:
            kgs = await service.list_all(
                user_id=current_user.user_id.value,
                permission=perm,
            )
        kg_responses = [KnowledgeGraphResponse.from_domain(kg) for kg in kgs]
        return KnowledgeGraphListResponse(
            knowledge_graphs=kg_responses,
            count=len(kg_responses),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list knowledge graphs",
        )


@router.get(
    "/knowledge-graphs/{kg_id}",
    response_model=KnowledgeGraphResponse,
    summary="Get knowledge graph by ID",
    description="""
Retrieve a knowledge graph by its ID.

Returns 404 if the knowledge graph does not exist or if the caller lacks `view`
access — no distinction is made to avoid leaking resource existence.
""",
    response_description="Knowledge graph details including name, workspace, and timestamps",
    responses={
        200: {"description": "Knowledge graph found and returned"},
        401: {"description": "Authentication required"},
        404: {"description": "Knowledge graph not found or caller lacks view access"},
        500: {"description": "Internal server error"},
    },
)
async def get_knowledge_graph(
    kg_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> KnowledgeGraphResponse:
    """Get a knowledge graph by ID."""
    try:
        kg = await service.get(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )

        if kg is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge graph {kg_id} not found",
            )

        return KnowledgeGraphResponse.from_domain(kg)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve knowledge graph",
        )


@router.post(
    "/workspaces/{workspace_id}/knowledge-graphs",
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_graph(
    workspace_id: str,
    request: CreateKnowledgeGraphRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> KnowledgeGraphResponse:
    """Create a new knowledge graph in a workspace.

    The current user must have EDIT permission on the target workspace.

    Args:
        workspace_id: The workspace to create the KG in
        request: Knowledge graph creation request (name, optional description)
        current_user: Current authenticated user with tenant context
        service: Knowledge graph service for orchestration

    Returns:
        KnowledgeGraphResponse with created KG details

    Raises:
        HTTPException: 403 if user lacks EDIT permission on the workspace
        HTTPException: 409 if a KG with this name already exists in the tenant
        HTTPException: 500 for unexpected errors
    """
    try:
        kg = await service.create(
            user_id=current_user.user_id.value,
            workspace_id=workspace_id,
            name=request.name,
            description=request.description,
        )
        return KnowledgeGraphResponse.from_domain(kg)

    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except DuplicateKnowledgeGraphNameError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A knowledge graph with this name already exists",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create knowledge graph",
        )


@router.get(
    "/workspaces/{workspace_id}/knowledge-graphs",
    response_model=KnowledgeGraphListResponse,
    summary="List knowledge graphs in a workspace",
    description="""
List all knowledge graphs within a workspace that the caller can view.

Requires `view` permission on the workspace. Results are filtered by
authorization — only knowledge graphs the caller can access are returned.
""",
    response_description="List of knowledge graphs with total count",
    responses={
        200: {"description": "Knowledge graphs listed successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions on the workspace"},
        500: {"description": "Internal server error"},
    },
)
async def list_workspace_knowledge_graphs(
    workspace_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> KnowledgeGraphListResponse:
    """List knowledge graphs in a workspace."""
    try:
        kgs = await service.list_for_workspace(
            user_id=current_user.user_id.value,
            workspace_id=workspace_id,
        )

        kg_responses = [KnowledgeGraphResponse.from_domain(kg) for kg in kgs]
        return KnowledgeGraphListResponse(
            knowledge_graphs=kg_responses,
            count=len(kg_responses),
        )

    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list knowledge graphs",
        )


@router.patch(
    "/knowledge-graphs/{kg_id}",
    response_model=KnowledgeGraphResponse,
    summary="Update knowledge graph metadata",
    description="""
Update the name and/or description of a knowledge graph.

Requires `edit` permission on the knowledge graph. The new name must be
unique within the tenant.
""",
    response_description="Updated knowledge graph details",
    responses={
        200: {"description": "Knowledge graph updated successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions on the knowledge graph"},
        404: {"description": "Knowledge graph not found"},
        409: {"description": "Knowledge graph name already exists in tenant"},
        422: {"description": "Validation error — name empty or exceeds 100 characters"},
        500: {"description": "Internal server error"},
    },
)
async def update_knowledge_graph(
    kg_id: str,
    request: UpdateKnowledgeGraphRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> KnowledgeGraphResponse:
    """Update a knowledge graph's metadata."""
    try:
        kg = await service.update(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
            name=request.name,
            description=request.description,
        )
        return KnowledgeGraphResponse.from_domain(kg)

    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except DuplicateKnowledgeGraphNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except KnowledgeGraphNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update knowledge graph",
        )


@router.get(
    "/knowledge-graphs/{kg_id}/ontology",
    response_model=OntologyConfigResponse,
    summary="Get ontology for a knowledge graph",
    description="""
Retrieve the stored ontology configuration for a knowledge graph.

Returns `200` with the OntologyConfig when an ontology has been saved.
Returns `404` when no ontology has been saved yet — this is the default
state for all knowledge graphs until a user approves a proposed ontology.

Requires `view` permission on the knowledge graph.
""",
    response_description="Stored ontology including node types, edge types, and approval state",
    responses={
        200: {"description": "Ontology found and returned"},
        401: {"description": "Authentication required"},
        404: {
            "description": "No ontology saved for this knowledge graph, or KG not found"
        },
        500: {"description": "Internal server error"},
    },
)
async def get_knowledge_graph_ontology(
    kg_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> OntologyConfigResponse:
    """Get the ontology configuration for a knowledge graph."""
    try:
        config = await service.get_ontology(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No ontology found for knowledge graph {kg_id}",
            )
        return OntologyConfigResponse.from_domain(config)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve ontology",
        )


@router.put(
    "/knowledge-graphs/{kg_id}/ontology",
    response_model=OntologyConfigResponse,
    summary="Save ontology for a knowledge graph",
    description="""
Save (full replace) the ontology configuration for a knowledge graph.

Stores the provided node types, edge types, and approval state. This is a
full replace — not a merge. The stored ontology can be retrieved later via
`GET /knowledge-graphs/{id}/ontology`.

Requires `edit` permission on the knowledge graph.
""",
    response_description="The stored ontology as persisted",
    responses={
        200: {"description": "Ontology saved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions — edit required"},
        404: {"description": "Knowledge graph not found"},
        422: {"description": "Validation error in request body"},
        500: {"description": "Internal server error"},
    },
)
async def save_knowledge_graph_ontology(
    kg_id: str,
    request: OntologyConfigRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> OntologyConfigResponse:
    """Save the ontology configuration for a knowledge graph."""
    try:
        config = await service.save_ontology(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
            config=request.to_domain(),
        )
        return OntologyConfigResponse.from_domain(config)

    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except KnowledgeGraphNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save ontology",
        )


@router.delete(
    "/knowledge-graphs/{kg_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a knowledge graph",
    description="""
Delete a knowledge graph and cascade-delete all of its data sources.

Requires `manage` permission on the knowledge graph. The deletion is atomic:
all data sources are removed along with the knowledge graph and all
authorization relationships in a single transaction.
""",
    response_description="No content returned on successful deletion",
    responses={
        204: {"description": "Knowledge graph deleted successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions on the knowledge graph"},
        404: {"description": "Knowledge graph not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_knowledge_graph(
    kg_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> None:
    """Delete a knowledge graph and cascade-delete its data sources."""
    try:
        deleted = await service.delete(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge graph {kg_id} not found",
            )

        return None

    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete knowledge graph",
        )
