"""Application-layer value objects for IAM bounded context.

These are value objects specific to the application layer, representing
cross-cutting concerns like authentication context.
"""

from __future__ import annotations

from dataclasses import dataclass

from iam.domain.value_objects import TenantId, UserId


@dataclass(frozen=True)
class CurrentUser:
    """Represents the currently authenticated user.

    This is extracted from authentication headers and used throughout
    the request lifecycle. In production, this comes from JWT claims.

    This is an application-layer concept (not domain) because it represents
    the authentication/authorization context of the request, not a core
    business entity.
    """

    user_id: UserId
    username: str
    tenant_id: TenantId
