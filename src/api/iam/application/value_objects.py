"""Application-layer value objects for IAM bounded context.

These are value objects specific to the application layer, representing
cross-cutting concerns like authentication context and read-only view objects.
"""

from __future__ import annotations

from dataclasses import dataclass

from iam.domain.value_objects import (
    GroupRole,
    MemberType,
    TenantId,
    UserId,
    WorkspaceRole,
)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Represents a user who has been authenticated but not yet scoped to a tenant.

    Used for endpoints that need authentication but not tenant context,
    such as listing available tenants or creating a new tenant. This solves
    the chicken-and-egg problem where users need to interact with tenant
    endpoints before they have a tenant context.

    This is an application-layer concept (not domain) because it represents
    the authentication context of the request, not a core business entity.
    """

    user_id: UserId
    username: str


@dataclass(frozen=True)
class CurrentUser:
    """Represents the currently authenticated user with tenant context.

    This is extracted from authentication headers and used throughout
    the request lifecycle. In production, this comes from JWT claims.

    This is an application-layer concept (not domain) because it represents
    the authentication/authorization context of the request, not a core
    business entity.
    """

    user_id: UserId
    username: str
    tenant_id: TenantId


@dataclass(frozen=True)
class GroupAccessGrant:
    """Represents a member's access grant on a group.

    This is a read-only view object returned from authorization queries.
    It captures who has what level of access to a group.

    Attributes:
        user_id: The user ID
        role: The group role (ADMIN or MEMBER)
    """

    user_id: str
    role: GroupRole


@dataclass(frozen=True)
class WorkspaceAccessGrant:
    """Represents a member's access grant on a workspace.

    This is a read-only view object returned from authorization queries.
    It captures who has what level of access to a workspace.

    Attributes:
        member_id: The user ID or group ID
        member_type: Whether this is a USER or GROUP grant
        role: The workspace role (ADMIN, EDITOR, or MEMBER)
    """

    member_id: str
    member_type: MemberType
    role: WorkspaceRole
