"""Request and response models for workspace API endpoints."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from iam.domain.aggregates import Workspace
from iam.domain.value_objects import MemberType, WorkspaceRole


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


class MemberTypeEnum(StrEnum):
    """API-level enum for member types.

    Maps to domain MemberType values for validation.
    """

    USER = "user"
    GROUP = "group"


class WorkspaceRoleEnum(StrEnum):
    """API-level enum for workspace roles.

    Maps to domain WorkspaceRole values for validation.
    """

    ADMIN = "admin"
    EDITOR = "editor"
    MEMBER = "member"


class AddWorkspaceMemberRequest(BaseModel):
    """Request model for adding a member to a workspace.

    Attributes:
        member_id: User ID or Group ID to add
        member_type: Type of member (user or group)
        role: Role to assign (admin, editor, or member)
    """

    member_id: str = Field(
        ...,
        description="User ID or Group ID to add as member",
        min_length=1,
        examples=["01HN3XQ7K2XYZ123456789ABCD", "engineering-group"],
    )
    member_type: MemberTypeEnum = Field(
        ...,
        description="Type of member being added",
        examples=["user", "group"],
    )
    role: WorkspaceRoleEnum = Field(
        ...,
        description="Role to assign to the member",
        examples=["admin", "editor", "member"],
    )

    def to_domain_member_type(self) -> MemberType:
        """Convert API member_type to domain MemberType.

        Returns:
            MemberType domain value object
        """
        return MemberType(self.member_type.value)

    def to_domain_role(self) -> WorkspaceRole:
        """Convert API role to domain WorkspaceRole.

        Returns:
            WorkspaceRole domain value object
        """
        return WorkspaceRole(self.role.value)


class WorkspaceMemberResponse(BaseModel):
    """Response model for a workspace member.

    Attributes:
        member_id: User ID or Group ID
        member_type: Type of member (user or group)
        role: Member's role in the workspace
    """

    member_id: str = Field(..., description="User ID or Group ID")
    member_type: str = Field(..., description="Type of member (user or group)")
    role: str = Field(..., description="Member's role in the workspace")

    @classmethod
    def from_tuple(cls, member: tuple[str, str, str]) -> WorkspaceMemberResponse:
        """Create from (member_id, member_type, role) tuple.

        Args:
            member: Tuple of (member_id, member_type, role) from service

        Returns:
            WorkspaceMemberResponse
        """
        return cls(
            member_id=member[0],
            member_type=member[1],
            role=member[2],
        )
