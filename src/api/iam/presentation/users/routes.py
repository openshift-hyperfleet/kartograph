"""Routes for user lookup endpoint.

Provides batch ID resolution and text search for users,
scoped to the caller's tenant via SpiceDB membership checks.

Spec: specs/iam/users.spec.md
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user, get_user_repository
from iam.domain.value_objects import UserId
from iam.infrastructure.user_repository import UserRepository
from iam.presentation.users.models import UserListResponse, UserProfileResponse
from infrastructure.authorization_dependencies import get_spicedb_client
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import ResourceType, format_resource

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserListResponse)
async def lookup_users(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    ids: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
) -> UserListResponse:
    """Look up users by batch IDs or text search.

    Exactly one of ``ids`` or ``search`` must be provided.
    Results are scoped to the caller's tenant membership.

    Args:
        current_user: The authenticated caller with tenant context
        user_repo: User repository for database queries
        authz: Authorization provider for tenant membership checks
        ids: Comma-separated list of user IDs to resolve (max 100)
        search: Text to search in username, name, and email (case-insensitive)

    Returns:
        UserListResponse with matching user profiles

    Raises:
        HTTPException 422: If params are missing, mutually exclusive, or exceed limits
    """
    # Validate: exactly one of ids or search must be provided
    if ids and search:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ids and search are mutually exclusive",
        )
    if not ids and not search:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either ids or search parameter is required",
        )

    # Get tenant member IDs from SpiceDB
    tenant_resource = format_resource(
        resource_type=ResourceType.TENANT,
        resource_id=current_user.tenant_id.value,
    )
    subject_relations = await authz.lookup_subjects(
        resource=tenant_resource,
        relation="member",
        subject_type="user",
    )
    tenant_member_set = {sr.subject_id for sr in subject_relations}

    if ids:
        id_list = [id_val.strip() for id_val in ids.split(",") if id_val.strip()]
        if len(id_list) > 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Maximum 100 IDs per request",
            )
        # Filter to only IDs that are tenant members
        scoped_ids = [UserId(value=uid) for uid in id_list if uid in tenant_member_set]
        if not scoped_ids:
            return UserListResponse(users=[], count=0)
        users = await user_repo.get_by_ids(scoped_ids)
    else:
        # search mode
        assert search is not None  # for type checker
        all_matches = await user_repo.search(search)
        # filter to tenant members
        users = [u for u in all_matches if u.id.value in tenant_member_set]

    profiles = [UserProfileResponse.from_domain(u) for u in users]
    return UserListResponse(users=profiles, count=len(profiles))
