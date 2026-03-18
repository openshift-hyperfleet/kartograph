"""Data source management routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from management.application.services.data_source_service import DataSourceService
from management.dependencies.data_source import get_data_source_service
from management.ports.exceptions import (
    DuplicateDataSourceNameError,
    UnauthorizedError,
)
from management.presentation.data_sources.models import (
    CreateDataSourceRequest,
    DataSourceListResponse,
    DataSourceResponse,
    SyncRunResponse,
    UpdateDataSourceRequest,
)
from shared_kernel.datasource_types import DataSourceAdapterType

router = APIRouter(tags=["Data Sources"])


@router.post(
    "/knowledge-graphs/{kg_id}/data-sources",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a data source",
)
async def create_data_source(
    kg_id: str,
    request: CreateDataSourceRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> DataSourceResponse:
    """Create a new data source in a knowledge graph."""
    try:
        adapter_type = DataSourceAdapterType(request.adapter_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid adapter type: {request.adapter_type}",
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
    except DuplicateDataSourceNameError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A data source with this name already exists in this knowledge graph",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/knowledge-graphs/{kg_id}/data-sources",
    response_model=DataSourceListResponse,
    summary="List data sources for a knowledge graph",
)
async def list_data_sources(
    kg_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> DataSourceListResponse:
    """List data sources for a knowledge graph with pagination."""
    try:
        all_ds = await service.list_for_knowledge_graph(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
        total = len(all_ds)
        paginated = all_ds[offset : offset + limit]
        return DataSourceListResponse(
            items=[DataSourceResponse.from_domain(ds) for ds in paginated],
            total=total,
            offset=offset,
            limit=limit,
        )
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )


@router.get(
    "/data-sources/{ds_id}",
    response_model=DataSourceResponse,
    summary="Get a data source by ID",
)
async def get_data_source(
    ds_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> DataSourceResponse:
    """Get a data source by ID."""
    try:
        ds = await service.get(user_id=current_user.user_id.value, ds_id=ds_id)
        if ds is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Data source not found",
            )
        return DataSourceResponse.from_domain(ds)
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )


@router.patch(
    "/data-sources/{ds_id}",
    response_model=DataSourceResponse,
    summary="Update a data source",
)
async def update_data_source(
    ds_id: str,
    request: UpdateDataSourceRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> DataSourceResponse:
    """Update a data source's configuration."""
    try:
        ds = await service.update(
            user_id=current_user.user_id.value,
            ds_id=ds_id,
            name=request.name,
            connection_config=request.connection_config,
            raw_credentials=request.credentials,
        )
        return DataSourceResponse.from_domain(ds)
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except DuplicateDataSourceNameError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A data source with this name already exists in this knowledge graph",
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Data source not found",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )


@router.delete(
    "/data-sources/{ds_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a data source",
)
async def delete_data_source(
    ds_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> None:
    """Delete a data source."""
    try:
        result = await service.delete(
            user_id=current_user.user_id.value,
            ds_id=ds_id,
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Data source not found",
            )
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


@router.post(
    "/data-sources/{ds_id}/sync",
    response_model=SyncRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a data source sync",
)
async def trigger_sync(
    ds_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> SyncRunResponse:
    """Trigger a sync for a data source."""
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
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found",
        )
