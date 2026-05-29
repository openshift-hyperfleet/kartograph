"""HTTP routes for Data Source management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from management.application.services.data_source_service import DataSourceService
from management.dependencies.data_source import (
    get_data_source_service,
    get_git_commit_reference_service,
    get_git_diff_summary_service,
    get_sync_run_repository,
)
from management.infrastructure.git_commit_reference_service import (
    GitCommitReferenceService,
)
from management.infrastructure.git_diff_summary_service import GitDiffSummaryService
from management.ports.exceptions import UnauthorizedError
from management.ports.repositories import IDataSourceSyncRunRepository
from management.presentation.data_sources.models import (
    CreateDataSourceRequest,
    DataSourceDiffSummaryResponse,
    DataSourceListResponse,
    DataSourceResponse,
    DataSourceWithSyncResponse,
    RunControlAction,
    RunControlResponse,
    MutationLogEntryPreviewPageResponse,
    SyncRunLogsResponse,
    SyncRunResponse,
    TriggerSyncRequest,
    UpdateDataSourceRequest,
)
from shared_kernel.datasource_types import DataSourceAdapterType

router = APIRouter(tags=["data-sources"])


def _build_operation_count_entry_previews(
    operation_counts: dict[str, int],
) -> list[tuple[int, str, str]]:
    """Expand operation counts into stable, per-entry preview rows."""
    previews: list[tuple[int, str, str]] = []
    line_number = 1
    for operation_class in sorted(operation_counts.keys()):
        raw_count = operation_counts.get(operation_class, 0)
        count = int(raw_count) if raw_count is not None else 0
        if count <= 0:
            continue
        for occurrence in range(1, count + 1):
            previews.append(
                (
                    line_number,
                    operation_class,
                    f"{operation_class} operation {occurrence} of {count}",
                )
            )
            line_number += 1
    return previews


@router.post(
    "/data-sources/{ds_id}/commit-refs/refresh",
    status_code=status.HTTP_200_OK,
    summary="Check remote branch tip and unpulled commits for a data source",
)
async def refresh_commit_references(
    ds_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
    commit_ref_service: Annotated[
        GitCommitReferenceService, Depends(get_git_commit_reference_service)
    ],
) -> DataSourceResponse:
    """Resolve the remote branch tip and whether we have unpulled commits.

    Updates ``tracked_branch_head_commit`` to the current GitHub branch HEAD
    (the commit ``git pull`` would fast-forward to). The response includes
    ``newest_unpulled_commit`` when that tip is ahead of our ingested head.
    """
    try:
        ds = await service.get(
            user_id=current_user.user_id.value,
            ds_id=ds_id,
        )
        if ds is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Data source not found",
            )

        tracked_head = await commit_ref_service.resolve_tracked_head_commit(ds)
        if tracked_head is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unable to resolve tracked branch head commit for this data source",
            )

        updated = await service.refresh_commit_references(
            user_id=current_user.user_id.value,
            ds_id=ds_id,
            tracked_branch_head_commit=tracked_head,
        )
        return DataSourceResponse.from_domain(updated)
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh commit references",
        )


@router.post(
    "/data-sources/{ds_id}/commit-refs/adopt-tracked-head",
    status_code=status.HTTP_200_OK,
    summary="Adopt tracked branch head as extraction baseline",
)
async def adopt_tracked_head_as_baseline(
    ds_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> DataSourceResponse:
    """Set extraction baseline commit to the current tracked branch head."""
    try:
        updated = await service.adopt_tracked_head_as_baseline(
            user_id=current_user.user_id.value,
            ds_id=ds_id,
        )
        return DataSourceResponse.from_domain(updated)
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except ValueError as e:
        detail = str(e)
        status_code = (
            status.HTTP_422_UNPROCESSABLE_ENTITY
            if "tracked branch head" in detail
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to adopt tracked head as baseline",
        )


@router.get(
    "/data-sources/{ds_id}/diff-summary",
    status_code=status.HTTP_200_OK,
    summary="Get commit diff summary for a data source",
)
async def get_diff_summary(
    ds_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
    diff_service: Annotated[
        GitDiffSummaryService, Depends(get_git_diff_summary_service)
    ],
    max_files: int = Query(default=200, ge=1, le=2000),
) -> DataSourceDiffSummaryResponse:
    """Return baseline-vs-tracked diff summary for maintenance readiness cues."""
    try:
        ds = await service.get(
            user_id=current_user.user_id.value,
            ds_id=ds_id,
        )
        if ds is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Data source not found",
            )

        summary = await diff_service.build_summary(
            data_source=ds,
            max_files=max_files,
        )
        return DataSourceDiffSummaryResponse(
            baseline_commit=summary.baseline_commit,
            tracked_head_commit=summary.tracked_head_commit,
            total_changed_files=summary.total_changed_files,
            added_count=summary.added_count,
            modified_count=summary.modified_count,
            removed_count=summary.removed_count,
            renamed_count=summary.renamed_count,
            files_truncated=summary.files_truncated,
            changed_files=list(summary.changed_files),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build diff summary",
        )


@router.get(
    "/data-sources",
    status_code=status.HTTP_200_OK,
    summary="List all data sources across the tenant",
    description="""
List all data sources accessible to the current user across all their knowledge graphs.

Includes the most recent sync run per data source embedded in the response, enabling
the sidebar navigation badge to reflect live sync state without additional API calls.

Only data sources belonging to knowledge graphs the user has VIEW permission on
are returned.
""",
)
async def list_all_data_sources(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> DataSourceListResponse:
    """List all data sources in the tenant with the latest sync run status.

    Args:
        current_user: Current authenticated user with tenant context
        service: Data source service for orchestration

    Returns:
        DataSourceListResponse with data_sources list and count

    Raises:
        HTTPException: 500 for unexpected errors
    """
    try:
        pairs = await service.list_all_for_user(user_id=current_user.user_id.value)
        responses = [
            DataSourceWithSyncResponse.from_domain_pair(pair) for pair in pairs
        ]
        return DataSourceListResponse(data_sources=responses, count=len(responses))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list data sources",
        )


@router.get(
    "/knowledge-graphs/{kg_id}/data-sources",
    status_code=status.HTTP_200_OK,
)
async def list_data_sources(
    kg_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> list[DataSourceResponse]:
    """List all data sources for a knowledge graph.

    The current user must have VIEW permission on the knowledge graph.

    Args:
        kg_id: Knowledge Graph ID to list data sources for
        current_user: Current authenticated user with tenant context
        service: Data source service for orchestration

    Returns:
        List of DataSourceResponse objects for the knowledge graph

    Raises:
        HTTPException: 403 if user lacks VIEW permission on the KG
        HTTPException: 500 for unexpected errors
    """
    try:
        data_sources = await service.list_for_knowledge_graph(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
        return [DataSourceResponse.from_domain(ds) for ds in data_sources]

    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list data sources",
        )


@router.post(
    "/knowledge-graphs/{kg_id}/data-sources",
    status_code=status.HTTP_201_CREATED,
)
async def create_data_source(
    kg_id: str,
    request: CreateDataSourceRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> DataSourceResponse:
    """Create a new data source in a knowledge graph.

    The current user must have EDIT permission on the target knowledge graph.

    Args:
        kg_id: The knowledge graph to create the DS in
        request: Data source creation request
        current_user: Current authenticated user with tenant context
        service: Data source service for orchestration

    Returns:
        DataSourceResponse with created DS details

    Raises:
        HTTPException: 403 if user lacks EDIT permission on the KG
        HTTPException: 404 if KG not found
        HTTPException: 500 for unexpected errors
    """
    try:
        adapter_type = DataSourceAdapterType(request.adapter_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported adapter_type: {request.adapter_type}",
        )

    try:
        ontology = (
            request.ontology.to_domain() if request.ontology is not None else None
        )
        ds = await service.create(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
            name=request.name,
            adapter_type=adapter_type,
            connection_config=request.connection_config,
            raw_credentials=request.credentials,
            ontology=ontology,
        )
        return DataSourceResponse.from_domain(ds)

    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create data source",
        )


@router.post(
    "/data-sources/{ds_id}/sync",
    status_code=status.HTTP_201_CREATED,
)
async def trigger_sync(
    ds_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
    body: TriggerSyncRequest | None = None,
) -> SyncRunResponse:
    """Trigger a synchronization for a data source.

    The current user must have MANAGE permission on the data source.
    Creates a new sync run and dispatches an event to start ingestion.

    Args:
        ds_id: Data Source ID to trigger sync for
        current_user: Current authenticated user with tenant context
        service: Data source service for orchestration
        body: Optional pipeline mode (default full sync)

    Returns:
        SyncRunResponse with the created sync run details

    Raises:
        HTTPException: 403 if user lacks MANAGE permission on the DS
        HTTPException: 404 if DS not found
        HTTPException: 500 for unexpected errors
    """
    request = body or TriggerSyncRequest()
    try:
        sync_run = await service.trigger_sync(
            user_id=current_user.user_id.value,
            ds_id=ds_id,
            pipeline_mode=request.mode,
        )
        return SyncRunResponse.from_domain(sync_run)

    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger sync",
        )


@router.get(
    "/data-sources/{ds_id}/sync-runs",
    status_code=status.HTTP_200_OK,
)
async def list_sync_runs(
    ds_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
    sync_run_repo: Annotated[
        IDataSourceSyncRunRepository, Depends(get_sync_run_repository)
    ],
) -> list[SyncRunResponse]:
    """List all sync runs for a data source.

    The current user must have VIEW permission on the data source (verified
    via service.get). The sync runs are then fetched from the repository.

    Args:
        ds_id: Data Source ID to list sync runs for
        current_user: Current authenticated user with tenant context
        service: Data source service for authorization check
        sync_run_repo: Sync run repository for listing runs

    Returns:
        List of SyncRunResponse objects for the data source

    Raises:
        HTTPException: 404 if DS not found or user lacks VIEW permission
        HTTPException: 500 for unexpected errors
    """
    try:
        # Verify user can VIEW the data source (service.get returns None if not authorized)
        ds = await service.get(
            user_id=current_user.user_id.value,
            ds_id=ds_id,
        )

        if ds is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Data source not found",
            )

        sync_runs = await sync_run_repo.find_by_data_source(ds_id)
        return [SyncRunResponse.from_domain(run) for run in sync_runs]

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list sync runs",
        )


@router.post(
    "/data-sources/{ds_id}/run-controls/{action}",
    status_code=status.HTTP_200_OK,
)
async def control_sync_runs(
    ds_id: str,
    action: RunControlAction,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> RunControlResponse:
    """Apply run-control action to extraction sync runs for a data source."""
    try:
        result = await service.apply_run_control(
            user_id=current_user.user_id.value,
            ds_id=ds_id,
            action=action,
        )
        return RunControlResponse(
            action=action,
            affected_count=result.affected_count,
            updated_runs=[SyncRunResponse.from_domain(run) for run in result.updated_runs],
            started_run=(
                SyncRunResponse.from_domain(result.started_run)
                if result.started_run is not None
                else None
            ),
        )
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except ValueError as e:
        detail = str(e)
        status_code = (
            status.HTTP_422_UNPROCESSABLE_ENTITY
            if "Unsupported run control action" in detail
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to apply run control action",
        )


@router.patch(
    "/data-sources/{ds_id}",
    response_model=DataSourceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a data source",
    description="""
Update the name and/or credentials of a data source.

Requires `edit` permission on the data source. Only the fields provided
are updated — omit a field to leave it unchanged.
""",
    response_description="Updated data source details",
    responses={
        200: {"description": "Data source updated successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions on the data source"},
        404: {"description": "Data source not found"},
        500: {"description": "Internal server error"},
    },
)
async def update_data_source(
    ds_id: str,
    request: UpdateDataSourceRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> DataSourceResponse:
    """Update a data source's configuration.

    Args:
        ds_id: Data Source ID to update
        request: Fields to update (all optional)
        current_user: Current authenticated user with tenant context
        service: Data source service for orchestration

    Returns:
        DataSourceResponse with updated DS details

    Raises:
        HTTPException: 403 if user lacks EDIT permission on the DS
        HTTPException: 404 if DS not found
        HTTPException: 500 for unexpected errors
    """
    try:
        ds = await service.update(
            user_id=current_user.user_id.value,
            ds_id=ds_id,
            name=request.name,
            connection_config=request.connection_config,
            raw_credentials=request.credentials,
        )

        if request.ontology is not None:
            ds = await service.update_ontology(
                user_id=current_user.user_id.value,
                ds_id=ds_id,
                ontology=request.ontology.to_domain(),
            )

        return DataSourceResponse.from_domain(ds)

    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update data source",
        )


@router.delete(
    "/data-sources/{ds_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a data source",
    description="""
Delete a data source and its associated credentials.

Requires `manage` permission on the data source. The deletion is
irreversible — all sync run history and stored credentials are removed.
""",
    response_description="No content returned on successful deletion",
    responses={
        204: {"description": "Data source deleted successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions on the data source"},
        404: {"description": "Data source not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_data_source(
    ds_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> None:
    """Delete a data source.

    Args:
        ds_id: Data Source ID to delete
        current_user: Current authenticated user with tenant context
        service: Data source service for orchestration

    Returns:
        None (204 No Content)

    Raises:
        HTTPException: 403 if user lacks MANAGE permission on the DS
        HTTPException: 404 if DS not found
        HTTPException: 500 for unexpected errors
    """
    try:
        deleted = await service.delete(
            user_id=current_user.user_id.value,
            ds_id=ds_id,
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data source {ds_id} not found",
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
            detail="Failed to delete data source",
        )


@router.get(
    "/data-sources/{ds_id}/sync-runs/{run_id}/logs",
    status_code=status.HTTP_200_OK,
)
async def get_sync_run_logs(
    ds_id: str,
    run_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
    sync_run_repo: Annotated[
        IDataSourceSyncRunRepository, Depends(get_sync_run_repository)
    ],
) -> SyncRunLogsResponse:
    """Get log lines for a specific sync run.

    The current user must have VIEW permission on the data source (enforced
    via service.get which returns None for unauthorized or missing resources).
    Verifies that the sync run belongs to the requested data source.

    Returns an empty list if no logs have been captured yet — this is correct
    until the Ingestion and Extraction contexts start populating logs.

    Args:
        ds_id: Data Source ID the sync run belongs to
        run_id: Sync Run ID to fetch logs for
        current_user: Current authenticated user with tenant context
        service: Data source service for authorization check
        sync_run_repo: Sync run repository for fetching the run

    Returns:
        SyncRunLogsResponse with ordered log lines (may be empty)

    Raises:
        HTTPException: 404 if DS not found, user lacks VIEW permission,
                       sync run not found, or run doesn't belong to this DS
        HTTPException: 500 for unexpected errors
    """
    try:
        # Verify user can VIEW the data source (returns None if not authorized)
        ds = await service.get(
            user_id=current_user.user_id.value,
            ds_id=ds_id,
        )

        if ds is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Data source not found",
            )

        # Fetch the sync run and verify it belongs to this data source
        sync_run = await sync_run_repo.get_by_id(run_id)

        if sync_run is None or sync_run.data_source_id != ds_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sync run not found",
            )

        return SyncRunLogsResponse(logs=sync_run.logs)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch sync run logs",
        )


@router.get(
    "/data-sources/{ds_id}/sync-runs/{run_id}/mutation-log-entries",
    status_code=status.HTTP_200_OK,
)
async def list_mutation_log_entry_previews(
    ds_id: str,
    run_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
    sync_run_repo: Annotated[
        IDataSourceSyncRunRepository, Depends(get_sync_run_repository)
    ],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MutationLogEntryPreviewPageResponse:
    """List paginated mutation-log entry previews for a sync run.

    Entry previews are derived from recorded per-run operation counts,
    giving users line-by-line visibility beyond aggregate totals.
    """
    try:
        ds = await service.get(
            user_id=current_user.user_id.value,
            ds_id=ds_id,
        )

        if ds is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Data source not found",
            )

        sync_run = await sync_run_repo.get_by_id(run_id)

        if sync_run is None or sync_run.data_source_id != ds_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sync run not found",
            )

        if sync_run.mutation_log_run is None:
            return MutationLogEntryPreviewPageResponse(
                entries=[],
                total=0,
                offset=offset,
                limit=limit,
                preview_available=False,
            )

        expanded_previews = _build_operation_count_entry_previews(
            sync_run.mutation_log_run.operation_counts
        )
        total = len(expanded_previews)
        page = expanded_previews[offset : offset + limit]

        return MutationLogEntryPreviewPageResponse(
            entries=[
                {
                    "line_number": line_number,
                    "operation_class": operation_class,
                    "summary": summary,
                }
                for line_number, operation_class, summary in page
            ],
            total=total,
            offset=offset,
            limit=limit,
            preview_available=total > 0,
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch mutation log entry previews",
        )
