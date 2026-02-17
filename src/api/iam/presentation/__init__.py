"""IAM presentation layer - aggregate-based organization.

Organizes presentation concerns by domain aggregate (groups, tenants, api_keys)
following vertical slicing and DDD principles. Each aggregate package contains
its own routes and models.
"""

from __future__ import annotations

from fastapi import APIRouter

from iam.presentation import api_keys, groups, tenants, workspaces

# Create main IAM router with common configuration.
# Auth is enforced per-endpoint (each handler declares its own Depends),
# not at the router level, to allow tenant-bootstrap endpoints (list/create
# tenants) to use get_authenticated_user instead of get_current_user.
router = APIRouter(
    prefix="/iam",
    tags=["iam"],
)

# Include all aggregate routers
router.include_router(groups.router)
router.include_router(tenants.router)
router.include_router(api_keys.router)
router.include_router(workspaces.router)

__all__ = ["router"]
