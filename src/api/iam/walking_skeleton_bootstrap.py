"""Walking skeleton bootstrap utilities for IAM bounded context.

TEMPORARY MODULE: This module facilitates the default tenant model used during
the walking skeleton/tracer bullet development approach. It provides a global
default tenant ID that simplifies development and testing.

This module is NOT intended for long-term use. It will be removed when:
- Multi-tenancy is fully implemented
- Users can belong to multiple tenants via SpiceDB
- Tenant context is resolved from JWT claims or request headers

Once proper multi-tenancy is in place, this module should be deleted and
references to it removed from the codebase.
"""

from __future__ import annotations

from iam.domain.value_objects import TenantId

# Module-level cache for default tenant ID (populated at startup)
_default_tenant_id: str | None = None


def set_default_tenant_id(tenant_id: TenantId) -> None:
    """Set the default tenant ID (called during app startup).

    This is a temporary convenience for the walking skeleton phase.
    Will be removed when proper multi-tenant resolution is implemented.

    Args:
        tenant_id: The default tenant ID to cache
    """
    global _default_tenant_id
    _default_tenant_id = tenant_id.value


def get_default_tenant_id() -> str:
    """Get the cached default tenant ID.

    This is a temporary convenience for the walking skeleton phase.
    Will be removed when proper multi-tenant resolution is implemented.

    Returns:
        The default tenant ID

    Raises:
        RuntimeError: If default tenant hasn't been initialized
    """
    if _default_tenant_id is None:
        raise RuntimeError(
            "Default tenant not initialized. Ensure app startup completed successfully."
        )
    return _default_tenant_id
