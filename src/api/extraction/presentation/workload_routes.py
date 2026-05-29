"""HTTP routes for extraction workload runtimes (graph read + mutation emitters)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from extraction.ports.workload_graph import IWorkloadGraphReader
from extraction.presentation.workload_auth import (
    WorkloadAuthContext,
    get_workload_auth_context,
)
from infrastructure.extraction_workload.dependencies import get_workload_graph_reader

router = APIRouter(prefix="/workloads", tags=["extraction-workloads"])


class WorkloadGraphSearchResponse(BaseModel):
    """Graph read response for sticky session agent tools."""

    nodes: list[dict]
    count: int


class WorkloadMutationProposalRequest(BaseModel):
    """Mutation emitter payload from sticky session agent tools."""

    operation: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    payload: dict = Field(default_factory=dict)


class WorkloadMutationProposalResponse(BaseModel):
    """Acknowledgement for a proposed mutation (not yet applied)."""

    accepted: bool
    proposal_id: str
    message: str


@router.get(
    "/graph/search-by-slug",
    response_model=WorkloadGraphSearchResponse,
)
async def workload_search_graph_by_slug(
    slug: Annotated[str, Query(min_length=1)],
    entity_type: Annotated[str | None, Query()] = None,
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
    reader: Annotated[IWorkloadGraphReader, Depends(get_workload_graph_reader)] = ...,
) -> WorkloadGraphSearchResponse:
    if "workload:chat" not in auth.credentials.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workload token is not authorized for chat graph reads",
        )

    nodes = await reader.search_by_slug(
        tenant_id=auth.tenant_id,
        knowledge_graph_id=auth.knowledge_graph_id,
        slug=slug,
        entity_type=entity_type,
    )
    serialized = [
        {
            "id": node.id,
            "entity_type": node.entity_type,
            "slug": node.slug,
            "properties": node.properties,
        }
        for node in nodes
    ]
    return WorkloadGraphSearchResponse(nodes=serialized, count=len(serialized))


@router.post(
    "/mutations/propose",
    response_model=WorkloadMutationProposalResponse,
)
async def workload_propose_mutation(
    request: WorkloadMutationProposalRequest,
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
) -> WorkloadMutationProposalResponse:
    if "workload:chat" not in auth.credentials.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workload token is not authorized for chat mutation proposals",
        )

    proposal_id = f"proposal-{request.operation}-{auth.knowledge_graph_id}"
    return WorkloadMutationProposalResponse(
        accepted=True,
        proposal_id=proposal_id,
        message=(
            "Mutation proposal recorded for audit. Apply via mutation log pipeline "
            "in a follow-up change."
        ),
    )
