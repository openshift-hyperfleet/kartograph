"""Tenant context value object for resolved tenant identification.

This module contains the pure value object that represents a resolved
tenant context. It is framework-agnostic and contains no business logic,
making it safe for the shared kernel.

The actual resolution logic (header extraction, ULID validation,
authorization checks) lives in the IAM bounded context's dependency layer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    """Resolved tenant context for the current request.

    This is a shared kernel value object used across bounded contexts
    to carry the resolved tenant identity.

    Attributes:
        tenant_id: The validated tenant identifier as a string.
        source: How the tenant was resolved - 'header' if from X-Tenant-ID,
            'default' if auto-selected in single-tenant mode.
    """

    tenant_id: str
    source: str
