"""HTTP routes for Data Source management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from management.application.services.data_source_service import DataSourceService
from management.dependencies.data_source import (
    get_data_source_service,
    get_sync_run_repository,
)
from management.presentation.auth_bridge import CurrentUser, get_current_user
from management.ports.exceptions import (
    KnowledgeGraphNotFoundError,
    UnauthorizedError,
)
from management.ports.repositories import IDataSourceSyncRunRepository
from management.presentation.data_sources.models import (
    CreateDataSourceRequest,
    DataSourceResponse,
    SyncRunResponse,
    UpdateDataSourceRequest,
)
from shared_kernel.datasource_types import DataSourceAdapterType

router = APIRouter(tags=["data-sources"])


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
        ds = await service.create(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
            name=request.name,
            adapter_type=adapter_type,
            connection_config=request.connection_config,
            raw_credentials=request.credentials,
        )
        return DataSourceResponse.from_domain(ds)

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
) -> SyncRunResponse:
    """Trigger a synchronization for a data source.

    The current user must have MANAGE permission on the data source.
    Creates a new sync run and dispatches an event to start ingestion.

    Args:
        ds_id: Data Source ID to trigger sync for
        current_user: Current authenticated user with tenant context
        service: Data source service for orchestration

    Returns:
        SyncRunResponse with the created sync run details

    Raises:
        HTTPException: 403 if user lacks MANAGE permission on the DS
        HTTPException: 404 if DS not found
        HTTPException: 500 for unexpected errors
    """
    try:
        sync_run = await service.trigger_sync(
            user_id=current_user.user_id.value,
            ds_id=ds_id,
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


@router.get(
    "/data-sources/{ds_id}",
    status_code=status.HTTP_200_OK,
)
async def get_data_source(
    ds_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> DataSourceResponse:
    """Get a data source by ID.

    Returns 404 if the data source does not exist or if the user lacks
    VIEW permission (to prevent existence leakage).

    Args:
        ds_id: Data Source ID (ULID format)
        current_user: Current authenticated user with tenant context
        service: Data source service for orchestration

    Returns:
        DataSourceResponse with DS details (never includes raw credentials)

    Raises:
        HTTPException: 404 if DS not found or user lacks VIEW permission
        HTTPException: 500 for unexpected errors
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

        return DataSourceResponse.from_domain(ds)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve data source",
        )


@router.patch(
    "/data-sources/{ds_id}",
    status_code=status.HTTP_200_OK,
)
async def update_data_source(
    ds_id: str,
    request: UpdateDataSourceRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> DataSourceResponse:
    """Update a data source's configuration.

    The current user must have EDIT permission on the data source.
    All request fields are optional — only provided fields are updated.
    The credentials_path is managed by the system and cannot be set directly.

    Args:
        ds_id: Data Source ID (ULID format)
        request: Update request with optional name, connection_config, credentials,
                 schedule_type, and schedule_value
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
            schedule_type=request.schedule_type,
            schedule_value=request.schedule_value,
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
)
async def delete_data_source(
    ds_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> None:
    """Delete a data source.

    The current user must have MANAGE permission on the data source.
    The operation deletes encrypted credentials first, then removes the
    data source record and cleans up authorization relationships (via outbox).

    Args:
        ds_id: Data Source ID (ULID format)
        current_user: Current authenticated user with tenant context
        service: Data source service for orchestration

    Returns:
        204 No Content on success

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
                detail="Data source not found",
            )

    except HTTPException:
        raise
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete data source",
        )
