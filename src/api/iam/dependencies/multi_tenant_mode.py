"""Multi-tenant mode gate dependency.

Provides a FastAPI dependency that blocks tenant management operations
(create, delete) when the application is running in single-tenant mode.

Usage in FastAPI routes:
    @router.post("", dependencies=[Depends(require_multi_tenant_mode)])
    async def create_tenant(...):
        ...
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from infrastructure.settings import IAMSettings, get_iam_settings


def _get_single_tenant_mode(
    settings: Annotated[IAMSettings, Depends(get_iam_settings)],
) -> bool:
    """Extract the single_tenant_mode flag from IAM settings.

    This is a thin sub-dependency so that unit tests can call
    ``require_multi_tenant_mode(single_tenant_mode=True)`` directly
    without constructing the full settings object.

    Args:
        settings: IAM settings instance.

    Returns:
        The value of settings.single_tenant_mode.
    """
    return settings.single_tenant_mode


def require_multi_tenant_mode(
    single_tenant_mode: Annotated[bool, Depends(_get_single_tenant_mode)],
) -> None:
    """Raise 403 if the application is running in single-tenant mode.

    This dependency should be applied to tenant management routes that
    must not be available in single-tenant deployments (e.g. create and
    delete tenant).

    Args:
        single_tenant_mode: Whether the application is in single-tenant mode,
            injected from IAMSettings.

    Raises:
        HTTPException 403: When single_tenant_mode is True.
    """
    if single_tenant_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant management is disabled in single-tenant mode",
        )
