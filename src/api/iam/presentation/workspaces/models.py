"""Request and response models for workspace API endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from iam.domain.aggregates import Workspace


class CreateWorkspaceRequest(BaseModel):
    """Request to create a child workspace.

    Attributes:
        name: Workspace name (1-512 characters)
        parent_workspace_id: Parent workspace ID (ULID format, 26 chars)
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Workspace name",
        examples=["Engineering", "Marketing", "Product"],
    )
    parent_workspace_id: str = Field(
        ...,
        min_length=26,
        max_length=26,
        description="Parent workspace ID (ULID)",
        examples=["01HN3XQ7K2XYZ123456789ABCD"],
    )


class WorkspaceResponse(BaseModel):
    """Response containing workspace details.

    Attributes:
        id: Workspace ID (ULID)
        tenant_id: Tenant ID this workspace belongs to
        name: Workspace name
        parent_workspace_id: Parent workspace ID (None for root)
        is_root: Whether this is the root workspace
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    id: str = Field(..., description="Workspace ID (ULID format)")
    tenant_id: str = Field(..., description="Tenant ID this workspace belongs to")
    name: str = Field(..., description="Workspace name")
    parent_workspace_id: str | None = Field(
        ..., description="Parent workspace ID (None for root)"
    )
    is_root: bool = Field(..., description="Whether this is the root workspace")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, workspace: Workspace) -> WorkspaceResponse:
        """Convert domain Workspace aggregate to API response.

        Args:
            workspace: Workspace domain aggregate

        Returns:
            WorkspaceResponse with workspace details
        """
        return cls(
            id=workspace.id.value,
            tenant_id=workspace.tenant_id.value,
            name=workspace.name,
            parent_workspace_id=workspace.parent_workspace_id.value
            if workspace.parent_workspace_id
            else None,
            is_root=workspace.is_root,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )


class WorkspaceListResponse(BaseModel):
    """Response containing list of workspaces.

    Attributes:
        workspaces: List of workspace details
        count: Number of workspaces returned
    """

    workspaces: list[WorkspaceResponse] = Field(
        ..., description="List of workspace details"
    )
    count: int = Field(..., description="Number of workspaces returned")
