"""HTTP routes for extraction workload runtimes (graph read + mutation emitters)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from extraction.ports.workload_graph import IWorkloadGraphReader
from extraction.ports.workload_schema import IWorkloadSchemaService
from extraction.presentation.workload_auth import (
    WorkloadAuthContext,
    get_workload_auth_context,
)
from infrastructure.extraction_workload.dependencies import (
    get_workload_graph_reader,
    get_workload_schema_service,
)
from management.domain.ontology_prepopulation import PrepopulationValidationError
from management.domain.value_objects import OntologyConfig

router = APIRouter(prefix="/workloads", tags=["extraction-workloads"])


def _require_chat_scope(auth: WorkloadAuthContext) -> None:
    if "workload:chat" not in auth.credentials.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workload token is not authorized for chat graph operations",
        )


class WorkloadGraphSearchResponse(BaseModel):
    """Graph read response for sticky session agent tools."""

    nodes: list[dict]
    count: int


class WorkloadOntologyResponse(BaseModel):
    """Canonical schema ontology for one knowledge graph."""

    knowledge_graph_id: str
    node_types: list[dict[str, Any]]
    edge_types: list[dict[str, Any]]
    approved_at: str | None = None


class WorkloadOntologySaveRequest(BaseModel):
    """Full ontology replace payload matching Management OntologyConfig."""

    node_types: list[dict[str, Any]] = Field(default_factory=list)
    edge_types: list[dict[str, Any]] = Field(default_factory=list)
    approved_at: str | None = None


class WorkloadMutationApplyRequest(BaseModel):
    """JSONL mutation batch for instance authoring or additive schema changes."""

    jsonl: str = Field(min_length=1)


class WorkloadMutationApplyResponse(BaseModel):
    """Result of applying a JSONL mutation batch."""

    applied: bool
    errors: list[str] = Field(default_factory=list)


class WorkloadSchemaAuthoringGuideResponse(BaseModel):
    """Authoring instructions surfaced to the Graph Management Assistant."""

    guide: str


@router.get(
    "/schema/authoring-guide",
    response_model=WorkloadSchemaAuthoringGuideResponse,
)
async def workload_schema_authoring_guide(
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
) -> WorkloadSchemaAuthoringGuideResponse:
    _require_chat_scope(auth)
    from extraction.application.schema_authoring_guide import SCHEMA_AUTHORING_GUIDE

    return WorkloadSchemaAuthoringGuideResponse(guide=SCHEMA_AUTHORING_GUIDE)


@router.get(
    "/schema/ontology",
    response_model=WorkloadOntologyResponse,
)
async def workload_get_schema_ontology(
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
    schema_service: Annotated[IWorkloadSchemaService, Depends(get_workload_schema_service)] = ...,
) -> WorkloadOntologyResponse:
    _require_chat_scope(auth)
    config = await schema_service.get_ontology(knowledge_graph_id=auth.knowledge_graph_id)
    if config is None:
        return WorkloadOntologyResponse(
            knowledge_graph_id=auth.knowledge_graph_id,
            node_types=[],
            edge_types=[],
            approved_at=None,
        )
    payload = config.to_dict()
    return WorkloadOntologyResponse(
        knowledge_graph_id=auth.knowledge_graph_id,
        node_types=list(payload.get("node_types", [])),
        edge_types=list(payload.get("edge_types", [])),
        approved_at=payload.get("approved_at"),
    )


@router.put(
    "/schema/ontology",
    response_model=WorkloadOntologyResponse,
)
async def workload_save_schema_ontology(
    request: WorkloadOntologySaveRequest,
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
    schema_service: Annotated[IWorkloadSchemaService, Depends(get_workload_schema_service)] = ...,
) -> WorkloadOntologyResponse:
    _require_chat_scope(auth)
    config = OntologyConfig.from_dict(request.model_dump())
    try:
        saved = await schema_service.replace_ontology(
            knowledge_graph_id=auth.knowledge_graph_id,
            config=config,
        )
    except PrepopulationValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    payload = saved.to_dict()
    return WorkloadOntologyResponse(
        knowledge_graph_id=auth.knowledge_graph_id,
        node_types=list(payload.get("node_types", [])),
        edge_types=list(payload.get("edge_types", [])),
        approved_at=payload.get("approved_at"),
    )


@router.post(
    "/mutations/apply",
    response_model=WorkloadMutationApplyResponse,
)
async def workload_apply_mutations(
    request: WorkloadMutationApplyRequest,
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
    schema_service: Annotated[IWorkloadSchemaService, Depends(get_workload_schema_service)] = ...,
) -> WorkloadMutationApplyResponse:
    _require_chat_scope(auth)
    result = await schema_service.apply_mutation_jsonl(
        tenant_id=auth.tenant_id,
        knowledge_graph_id=auth.knowledge_graph_id,
        jsonl=request.jsonl,
    )
    return WorkloadMutationApplyResponse(
        applied=bool(result.get("applied")),
        errors=[str(item) for item in result.get("errors", [])],
    )


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
    _require_chat_scope(auth)

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
