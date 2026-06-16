"""HTTP routes for extraction job configuration and execution."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from infrastructure.management.extraction_jobs_service import ExtractionJobsService
from infrastructure.management.extraction_jobs_dependencies import get_extraction_jobs_service
from management.ports.exceptions import UnauthorizedError

router = APIRouter(tags=["extraction-jobs"])


class ExtractionJobSetModel(BaseModel):
    name: str
    strategy: str
    enabled: bool = True
    description: str | None = None
    entity_type: str | None = None
    instances_per_job: int | None = None
    file_patterns: list[str] = Field(default_factory=list)
    files_per_job: int | None = None


class ExtractionJobsDocumentRequest(BaseModel):
    version: str = "1.0"
    job_sets: list[ExtractionJobSetModel] = Field(default_factory=list)


class ExtractionJobsDocumentResponse(BaseModel):
    version: str
    job_sets: list[dict[str, Any]]
    entity_types: list[dict[str, Any]] = Field(default_factory=list)


class StartExtractionRequest(BaseModel):
    workers: int = Field(default=20, ge=1, le=50)


class ActionResponse(BaseModel):
    success: bool
    message: str | None = None
    generated_jobs: int | None = None
    reset_count: int | None = None
    archived_count: int | None = None
    warnings: list[str] = Field(default_factory=list)


def _handle_value_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get(
    "/knowledge-graphs/{kg_id}/extraction-jobs",
    response_model=ExtractionJobsDocumentResponse,
)
async def get_extraction_jobs(
    kg_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ExtractionJobsDocumentResponse:
    try:
        payload = await service.get_extraction_jobs_document(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge graph not found")
    return ExtractionJobsDocumentResponse.model_validate(payload)


@router.put(
    "/knowledge-graphs/{kg_id}/extraction-jobs",
    response_model=ExtractionJobsDocumentResponse,
)
async def save_extraction_jobs(
    kg_id: str,
    body: ExtractionJobsDocumentRequest,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ExtractionJobsDocumentResponse:
    try:
        saved = await service.save_extraction_jobs_document(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
            payload=body.model_dump(),
        )
        regenerated = await service.regenerate_jobs(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    except ValueError as exc:
        raise _handle_value_error(exc)
    payload = await service.get_extraction_jobs_document(
        user_id=current_user.user_id.value,
        kg_id=kg_id,
    )
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge graph not found")
    payload["last_regenerated_jobs"] = regenerated.get("generated_jobs")
    payload["last_regenerate_warnings"] = regenerated.get("warnings")
    payload["last_regenerate_message"] = regenerated.get("message")
    return ExtractionJobsDocumentResponse.model_validate(payload)


@router.post(
    "/knowledge-graphs/{kg_id}/extraction-jobs/regenerate",
    response_model=ActionResponse,
)
async def regenerate_extraction_jobs(
    kg_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ActionResponse:
    try:
        result = await service.regenerate_jobs(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    except ValueError as exc:
        raise _handle_value_error(exc)
    return ActionResponse(
        success=True,
        message=str(result.get("message") or f"Regenerated {result.get('generated_jobs', 0)} jobs"),
        generated_jobs=int(result.get("generated_jobs") or 0),
        warnings=[str(item) for item in result.get("warnings") or []],
    )


@router.post(
    "/knowledge-graphs/{kg_id}/extraction-jobs/jobs/{job_id}/cancel",
    response_model=ActionResponse,
)
async def cancel_extraction_job(
    kg_id: str,
    job_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ActionResponse:
    try:
        result = await service.cancel_job(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
            job_id=job_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    except ValueError as exc:
        raise _handle_value_error(exc)
    return ActionResponse(success=True, message=result.get("message"))


@router.get("/knowledge-graphs/{kg_id}/extraction-jobs/jobs/{job_id}")
async def get_extraction_job_detail(
    kg_id: str,
    job_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    try:
        payload = await service.get_job_detail(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
            job_id=job_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extraction job not found")
    return payload


@router.get("/knowledge-graphs/{kg_id}/extraction-jobs/jobs/{job_id}/activity")
async def get_extraction_job_activity(
    kg_id: str,
    job_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    try:
        payload = await service.get_job_activity(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
            job_id=job_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extraction job not found")
    return payload


@router.get("/knowledge-graphs/{kg_id}/extraction-jobs/archived-history")
async def get_archived_extraction_history(
    kg_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    try:
        payload = await service.get_archived_extraction_history(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge graph not found")
    return payload


@router.get("/knowledge-graphs/{kg_id}/extraction-jobs/jobs/{job_id}/archived-mutations")
async def get_archived_job_mutations(
    kg_id: str,
    job_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    try:
        payload = await service.get_archived_job_mutations(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
            job_id=job_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archived job not found")
    return payload


@router.get("/knowledge-graphs/{kg_id}/extraction-jobs/database-status")
async def get_extraction_database_status(
    kg_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    try:
        payload = await service.get_database_status(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge graph not found")
    return payload


@router.get("/knowledge-graphs/{kg_id}/extraction-jobs/run-state")
async def get_extraction_run_state(
    kg_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    try:
        payload = await service.get_extraction_run_state(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge graph not found")
    return payload


@router.get("/knowledge-graphs/{kg_id}/extraction-jobs/plan-summary")
async def get_extraction_plan_summary(
    kg_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    try:
        payload = await service.get_extraction_plan_summary(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge graph not found")
    return payload


@router.post("/knowledge-graphs/{kg_id}/extraction-jobs/start", response_model=ActionResponse)
async def start_extraction(
    kg_id: str,
    body: StartExtractionRequest,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ActionResponse:
    try:
        result = await service.start_extraction(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
            workers=body.workers,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    except ValueError as exc:
        raise _handle_value_error(exc)
    return ActionResponse(success=True, message=result.get("message"))


@router.post("/knowledge-graphs/{kg_id}/extraction-jobs/pause", response_model=ActionResponse)
async def pause_extraction(
    kg_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ActionResponse:
    try:
        result = await service.pause_extraction(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    except ValueError as exc:
        raise _handle_value_error(exc)
    return ActionResponse(success=True, message=result.get("message"))


@router.post("/knowledge-graphs/{kg_id}/extraction-jobs/halt", response_model=ActionResponse)
async def halt_extraction(
    kg_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ActionResponse:
    try:
        result = await service.halt_extraction(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    except ValueError as exc:
        raise _handle_value_error(exc)
    return ActionResponse(success=True, message=result.get("message"))


@router.post("/knowledge-graphs/{kg_id}/extraction-jobs/reset-stale", response_model=ActionResponse)
async def reset_stale_jobs(
    kg_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ActionResponse:
    try:
        result = await service.reset_stale_jobs(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return ActionResponse(success=True, reset_count=int(result.get("reset_count") or 0))


@router.post("/knowledge-graphs/{kg_id}/extraction-jobs/reset-completed", response_model=ActionResponse)
async def reset_completed_jobs(
    kg_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ActionResponse:
    try:
        result = await service.reset_completed_jobs(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return ActionResponse(success=True, reset_count=int(result.get("reset_count") or 0))


@router.post("/knowledge-graphs/{kg_id}/extraction-jobs/archive-completed", response_model=ActionResponse)
async def archive_completed_jobs(
    kg_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ActionResponse:
    try:
        result = await service.archive_completed_jobs(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return ActionResponse(
        success=True,
        message=result.get("message"),
        archived_count=int(result.get("archived_count") or 0),
    )


@router.post("/knowledge-graphs/{kg_id}/extraction-jobs/reset-failed", response_model=ActionResponse)
async def reset_failed_jobs(
    kg_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ActionResponse:
    try:
        result = await service.reset_failed_jobs(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return ActionResponse(success=True, reset_count=int(result.get("reset_count") or 0))


@router.post("/knowledge-graphs/{kg_id}/extraction-jobs/reset", response_model=ActionResponse)
async def reset_extraction_jobs(
    kg_id: str,
    service: Annotated[ExtractionJobsService, Depends(get_extraction_jobs_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ActionResponse:
    try:
        result = await service.reset_extraction(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
    except UnauthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return ActionResponse(success=True, reset_count=int(result.get("reset_count") or 0))
