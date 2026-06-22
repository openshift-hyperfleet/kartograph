"""HTTP routes for extraction workload runtimes (graph read + mutation emitters)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from extraction.ports.workload_extraction_jobs import IWorkloadExtractionJobsService
from extraction.ports.workload_graph import IWorkloadGraphReader
from extraction.ports.workload_schema import IWorkloadSchemaService
from extraction.presentation.workload_auth import (
    WorkloadAuthContext,
    get_workload_auth_context,
    require_workload_admin_scope,
    require_workload_read_scope,
    require_workload_write_scope,
)
from infrastructure.extraction_workload.dependencies import (
    get_graph_management_session_journal_service,
    get_workload_extraction_jobs_service,
    get_workload_graph_reader,
    get_workload_schema_service,
)
from extraction.application.graph_management_session_journal import (
    GraphManagementSessionJournalService,
)
from infrastructure.extraction_workload.workload_errors import raise_graph_storage_http_error
from management.domain.ontology_prepopulation import PrepopulationValidationError
from management.domain.relationship_pairing import ontology_config_from_authoring_payload
from management.ports.exceptions import CanonicalSchemaMutationError

router = APIRouter(prefix="/workloads", tags=["extraction-workloads"])


async def _await_graph_operation(awaitable):
    """Run a graph-backed coroutine and map storage failures to HTTP 503."""
    try:
        return await awaitable
    except Exception as exc:
        raise_graph_storage_http_error(exc)


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


class WorkloadMutationValidateRequest(BaseModel):
    """JSONL mutation batch to validate without applying."""

    jsonl: str = Field(min_length=1)


class WorkloadMutationApplyResponse(BaseModel):
    """Result of applying a JSONL mutation batch."""

    applied: bool
    errors: list[str] = Field(default_factory=list)
    operations_applied: int = 0
    next_action: str = ""
    remaining_entity_gaps: list[str] = Field(default_factory=list)
    remaining_relationship_gaps: list[str] = Field(default_factory=list)


class WorkloadMutationValidateResponse(BaseModel):
    """Dry-run validation result for a JSONL mutation batch."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    operation_count: int = 0


class WorkloadSchemaAuthoringGuideResponse(BaseModel):
    """Authoring instructions surfaced to the Graph Management Assistant."""

    guide: str


class WorkloadInstanceListResponse(BaseModel):
    """Paginated entity instances for one type."""

    entity_type: str
    nodes: list[dict]
    count: int
    total: int
    limit: int
    offset: int


class WorkloadReadinessResponse(BaseModel):
    """Bootstrap readiness snapshot for schema prepopulation."""

    knowledge_graph_id: str
    has_minimum_entity_types: bool
    has_minimum_relationship_types: bool
    prepopulated_types_ready_metadata: bool
    prepopulated_types_without_instances_metadata: list[str] = Field(default_factory=list)
    prepopulated_relationship_types_without_instances_metadata: list[str] = Field(
        default_factory=list
    )
    prepopulated_entity_types_without_instances_live: list[str] = Field(default_factory=list)
    prepopulated_relationship_types_without_instances_live: list[str] = Field(
        default_factory=list
    )
    prepopulated_types_ready_live: bool = False
    prepopulated_entity_types: list[dict[str, object]] = Field(default_factory=list)
    prepopulated_relationship_types: list[dict[str, object]] = Field(default_factory=list)
    prepopulation_tasks: list[dict[str, object]] = Field(default_factory=list)
    next_action: str = ""
    blocking_reasons: list[str] = Field(default_factory=list)
    transition_eligible: bool


class WorkloadRelationshipListResponse(BaseModel):
    """Paginated relationship instances for one type."""

    relationship_type: str
    source_entity_type: str | None = None
    target_entity_type: str | None = None
    relationships: list[dict]
    count: int
    total: int
    limit: int
    offset: int


@router.get(
    "/schema/authoring-guide",
    response_model=WorkloadSchemaAuthoringGuideResponse,
)
async def workload_schema_authoring_guide(
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
) -> WorkloadSchemaAuthoringGuideResponse:
    require_workload_read_scope(auth)
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
    require_workload_read_scope(auth)
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
    require_workload_admin_scope(auth)
    config = ontology_config_from_authoring_payload(request.model_dump())
    try:
        saved = await schema_service.replace_ontology(
            knowledge_graph_id=auth.knowledge_graph_id,
            config=config,
        )
    except (PrepopulationValidationError, CanonicalSchemaMutationError) as e:
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
    "/mutations/validate",
    response_model=WorkloadMutationValidateResponse,
)
async def workload_validate_mutations(
    request: WorkloadMutationValidateRequest,
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
    schema_service: Annotated[IWorkloadSchemaService, Depends(get_workload_schema_service)] = ...,
) -> WorkloadMutationValidateResponse:
    require_workload_read_scope(auth)
    try:
        result = await schema_service.validate_mutation_jsonl(
            tenant_id=auth.tenant_id,
            knowledge_graph_id=auth.knowledge_graph_id,
            jsonl=request.jsonl,
        )
    except Exception as exc:
        raise_graph_storage_http_error(exc)
    return WorkloadMutationValidateResponse(
        valid=bool(result.get("valid")),
        errors=[str(item) for item in result.get("errors", [])],
        operation_count=int(result.get("operation_count", 0)),
    )


@router.post(
    "/mutations/apply",
    response_model=WorkloadMutationApplyResponse,
)
async def workload_apply_mutations(
    request: WorkloadMutationApplyRequest,
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
    schema_service: Annotated[IWorkloadSchemaService, Depends(get_workload_schema_service)] = ...,
    reader: Annotated[IWorkloadGraphReader, Depends(get_workload_graph_reader)] = ...,
    session_journal: Annotated[
        GraphManagementSessionJournalService,
        Depends(get_graph_management_session_journal_service),
    ] = ...,
) -> WorkloadMutationApplyResponse:
    require_workload_write_scope(auth)
    try:
        result = await schema_service.apply_mutation_jsonl(
            tenant_id=auth.tenant_id,
            knowledge_graph_id=auth.knowledge_graph_id,
            jsonl=request.jsonl,
        )
    except Exception as exc:
        raise_graph_storage_http_error(exc)

    next_action = ""
    remaining_entity_gaps: list[str] = []
    remaining_relationship_gaps: list[str] = []
    if result.get("applied"):
        applied_jsonl = str(result.get("applied_jsonl") or "").strip()
        instance_changes_jsonl = str(result.get("instance_changes_jsonl") or "").strip()
        if auth.session_id and applied_jsonl:
            await session_journal.append_applied_jsonl(
                tenant_id=auth.tenant_id,
                knowledge_graph_id=auth.knowledge_graph_id,
                session_id=auth.session_id,
                applied_jsonl=applied_jsonl,
            )
        if auth.session_id and instance_changes_jsonl:
            await session_journal.append_instance_changes(
                tenant_id=auth.tenant_id,
                knowledge_graph_id=auth.knowledge_graph_id,
                session_id=auth.session_id,
                instance_changes_jsonl=instance_changes_jsonl,
            )
        if auth.job_id and (applied_jsonl or instance_changes_jsonl):
            from extraction.infrastructure.job_mutation_artifact_store import (
                append_job_mutation_artifacts,
            )

            append_job_mutation_artifacts(
                knowledge_graph_id=auth.knowledge_graph_id,
                job_id=auth.job_id,
                applied_jsonl=applied_jsonl or None,
                instance_changes_jsonl=instance_changes_jsonl or None,
            )

        from infrastructure.extraction_workload.workspace_readiness import (
            build_workload_readiness_snapshot,
        )

        ontology = await schema_service.get_ontology(knowledge_graph_id=auth.knowledge_graph_id)
        try:
            snapshot = await build_workload_readiness_snapshot(
                ontology=ontology,
                knowledge_graph_id=auth.knowledge_graph_id,
                tenant_id=auth.tenant_id,
                graph_reader=reader,
            )
        except Exception as exc:
            raise_graph_storage_http_error(exc)
        next_action = str(snapshot.get("next_action") or "")
        remaining_entity_gaps = list(
            snapshot.get("prepopulated_entity_types_without_instances_live") or []
        )
        remaining_relationship_gaps = list(
            snapshot.get("prepopulated_relationship_types_without_instances_live") or []
        )

    return WorkloadMutationApplyResponse(
        applied=bool(result.get("applied")),
        errors=[str(item) for item in result.get("errors", [])],
        operations_applied=int(result.get("operations_applied", 0)),
        next_action=next_action,
        remaining_entity_gaps=remaining_entity_gaps,
        remaining_relationship_gaps=remaining_relationship_gaps,
    )


class WorkloadCheckSlugsRequest(BaseModel):
    """Batch slug existence check for one entity type."""

    entity_type: str = Field(min_length=1)
    slugs: list[str] = Field(min_length=1)


class WorkloadCheckSlugsResponse(BaseModel):
    """Partition of requested slugs into existing and missing."""

    entity_type: str
    existing_slugs: list[str] = Field(default_factory=list)
    missing_slugs: list[str] = Field(default_factory=list)


@router.post(
    "/graph/check-slugs",
    response_model=WorkloadCheckSlugsResponse,
)
async def workload_check_slugs(
    request: WorkloadCheckSlugsRequest,
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
    reader: Annotated[IWorkloadGraphReader, Depends(get_workload_graph_reader)] = ...,
) -> WorkloadCheckSlugsResponse:
    require_workload_read_scope(auth)
    normalized = tuple(
        sorted({str(slug).strip() for slug in request.slugs if str(slug).strip()})
    )
    existing, missing = await _await_graph_operation(
        reader.partition_slugs_by_existence(
            tenant_id=auth.tenant_id,
            knowledge_graph_id=auth.knowledge_graph_id,
            entity_type=request.entity_type.strip(),
            slugs=normalized,
        )
    )
    return WorkloadCheckSlugsResponse(
        entity_type=request.entity_type.strip(),
        existing_slugs=existing,
        missing_slugs=missing,
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
    require_workload_read_scope(auth)

    nodes = await _await_graph_operation(
        reader.search_by_slug(
            tenant_id=auth.tenant_id,
            knowledge_graph_id=auth.knowledge_graph_id,
            slug=slug,
            entity_type=entity_type,
        )
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


@router.get(
    "/graph/instances",
    response_model=WorkloadInstanceListResponse,
)
async def workload_list_instances_by_type(
    entity_type: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
    reader: Annotated[IWorkloadGraphReader, Depends(get_workload_graph_reader)] = ...,
) -> WorkloadInstanceListResponse:
    require_workload_read_scope(auth)

    nodes, total = await _await_graph_operation(
        reader.list_instances_by_type(
            tenant_id=auth.tenant_id,
            knowledge_graph_id=auth.knowledge_graph_id,
            entity_type=entity_type,
            limit=limit,
            offset=offset,
        )
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
    return WorkloadInstanceListResponse(
        entity_type=entity_type,
        nodes=serialized,
        count=len(serialized),
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/graph/relationships",
    response_model=WorkloadRelationshipListResponse,
)
async def workload_list_relationship_instances(
    relationship_type: Annotated[str, Query(min_length=1)],
    source_entity_type: Annotated[str | None, Query()] = None,
    target_entity_type: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
    reader: Annotated[IWorkloadGraphReader, Depends(get_workload_graph_reader)] = ...,
) -> WorkloadRelationshipListResponse:
    require_workload_read_scope(auth)

    relationships, total = await _await_graph_operation(
        reader.list_relationship_instances(
            tenant_id=auth.tenant_id,
            knowledge_graph_id=auth.knowledge_graph_id,
            relationship_type=relationship_type,
            source_entity_type=source_entity_type,
            target_entity_type=target_entity_type,
            limit=limit,
            offset=offset,
        )
    )
    serialized = [
        {
            "id": rel.id,
            "relationship_type": rel.relationship_type,
            "start_id": rel.start_id,
            "end_id": rel.end_id,
            "source_slug": rel.source_slug,
            "target_slug": rel.target_slug,
            "source_entity_type": rel.source_entity_type,
            "target_entity_type": rel.target_entity_type,
            "properties": rel.properties,
        }
        for rel in relationships
    ]
    return WorkloadRelationshipListResponse(
        relationship_type=relationship_type,
        source_entity_type=source_entity_type,
        target_entity_type=target_entity_type,
        relationships=serialized,
        count=len(serialized),
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/schema/readiness",
    response_model=WorkloadReadinessResponse,
)
async def workload_get_workspace_readiness(
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
    schema_service: Annotated[IWorkloadSchemaService, Depends(get_workload_schema_service)] = ...,
    reader: Annotated[IWorkloadGraphReader, Depends(get_workload_graph_reader)] = ...,
) -> WorkloadReadinessResponse:
    require_workload_read_scope(auth)
    from infrastructure.extraction_workload.workspace_readiness import (
        build_workload_readiness_snapshot,
    )

    ontology = await schema_service.get_ontology(knowledge_graph_id=auth.knowledge_graph_id)
    try:
        snapshot = await build_workload_readiness_snapshot(
            ontology=ontology,
            knowledge_graph_id=auth.knowledge_graph_id,
            tenant_id=auth.tenant_id,
            graph_reader=reader,
        )
    except Exception as exc:
        raise_graph_storage_http_error(exc)
    return WorkloadReadinessResponse(**snapshot)


class WorkloadExtractionJobsDocumentRequest(BaseModel):
    """Extraction job set configuration matching the management extraction-jobs API."""

    version: str = "1.0"
    job_sets: list[dict[str, Any]] = Field(default_factory=list)


class WorkloadExtractionJobsDocumentResponse(BaseModel):
    """Saved extraction job sets plus entity type counts."""

    version: str
    job_sets: list[dict[str, Any]]
    entity_types: list[dict[str, Any]] = Field(default_factory=list)
    generated_jobs: int | None = None


@router.get(
    "/extraction-jobs",
    response_model=WorkloadExtractionJobsDocumentResponse,
)
async def workload_get_extraction_jobs(
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
    service: Annotated[
        IWorkloadExtractionJobsService, Depends(get_workload_extraction_jobs_service)
    ] = ...,
) -> WorkloadExtractionJobsDocumentResponse:
    require_workload_read_scope(auth)
    try:
        payload = await service.get_document(
            tenant_id=auth.tenant_id,
            knowledge_graph_id=auth.knowledge_graph_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return WorkloadExtractionJobsDocumentResponse.model_validate(payload)


@router.put(
    "/extraction-jobs",
    response_model=WorkloadExtractionJobsDocumentResponse,
)
async def workload_save_extraction_jobs(
    request: WorkloadExtractionJobsDocumentRequest,
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
    service: Annotated[
        IWorkloadExtractionJobsService, Depends(get_workload_extraction_jobs_service)
    ] = ...,
) -> WorkloadExtractionJobsDocumentResponse:
    require_workload_admin_scope(auth)
    try:
        payload = await service.save_document(
            tenant_id=auth.tenant_id,
            knowledge_graph_id=auth.knowledge_graph_id,
            payload=request.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return WorkloadExtractionJobsDocumentResponse.model_validate(payload)


@router.get("/extraction-jobs/plan-summary")
async def workload_get_extraction_jobs_plan_summary(
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
    service: Annotated[
        IWorkloadExtractionJobsService, Depends(get_workload_extraction_jobs_service)
    ] = ...,
) -> dict[str, Any]:
    require_workload_read_scope(auth)
    try:
        return await service.get_plan_summary(
            tenant_id=auth.tenant_id,
            knowledge_graph_id=auth.knowledge_graph_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/extraction-jobs/status")
async def workload_get_extraction_jobs_status(
    auth: Annotated[WorkloadAuthContext, Depends(get_workload_auth_context)] = ...,
    service: Annotated[
        IWorkloadExtractionJobsService, Depends(get_workload_extraction_jobs_service)
    ] = ...,
) -> dict[str, Any]:
    require_workload_read_scope(auth)
    try:
        return await service.get_database_status(
            tenant_id=auth.tenant_id,
            knowledge_graph_id=auth.knowledge_graph_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
