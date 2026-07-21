"""HTTP routes for local agent poll/claim/heartbeat/complete/fail calls.

See specs/extraction/local-sandbox-execution.spec.md. Local agents
authenticate with the same `X-API-Key` mechanism as any other programmatic
Kartograph client (`iam/api-keys.spec.md`) via `get_current_user` -- no new
authentication mechanism is introduced for this bounded context.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from extraction.application.local_runtime_agent_service import (
    LocalRuntimeAgentService,
    LocalRuntimeWorkRequestNotClaimableError,
)
from extraction.dependencies import get_local_runtime_agent_service
from extraction.presentation.local_runtime_models import (
    LocalRuntimeCompleteRequest,
    LocalRuntimeFailRequest,
    LocalRuntimeWorkRequestResponse,
)
from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from infrastructure.authorization_dependencies import get_spicedb_client
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)

router = APIRouter(prefix="/local-runtime", tags=["extraction-local-runtime"])


async def _has_kg_edit_permission(
    *,
    authz: AuthorizationProvider,
    current_user: CurrentUser,
    knowledge_graph_id: str,
) -> bool:
    subject = format_subject(ResourceType.USER, current_user.user_id.value)
    resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, knowledge_graph_id)
    return await authz.check_permission(resource, Permission.EDIT, subject)


@router.post("/poll", status_code=status.HTTP_200_OK)
async def poll_for_work(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[
        LocalRuntimeAgentService, Depends(get_local_runtime_agent_service)
    ],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
) -> Response:
    """Claim the next pending work request for the authenticated user, if any.

    Always records presence, even when no work is claimed, so absence
    detection (specs "Local Agent Presence Tracking") reflects every poll.
    Returns 200 with the claimed request, or 204 with no body when there is
    nothing to do this cycle -- returning a `Response` directly (rather than
    relying on `response_model`) so the 204 case has a genuinely empty body.
    """
    claimed = await service.poll_and_claim(
        user_id=current_user.user_id.value,
        tenant_id=current_user.tenant_id.value,
    )
    if claimed is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    allowed = await _has_kg_edit_permission(
        authz=authz,
        current_user=current_user,
        knowledge_graph_id=claimed.knowledge_graph_id,
    )
    if not allowed:
        # specs "Claim revalidates authorization": a permission that held
        # when the request was created may no longer hold at claim time.
        # Fail the request rather than handing Sandbox work to an agent
        # whose user can no longer edit this knowledge graph, and tell the
        # agent there is nothing to do this cycle.
        await service.reject_claim(
            request_id=claimed.id,
            user_id=current_user.user_id.value,
            reason=(
                "Caller no longer has edit permission on knowledge graph "
                f"{claimed.knowledge_graph_id!r}."
            ),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    payload = LocalRuntimeWorkRequestResponse.from_domain(claimed)
    return JSONResponse(content=jsonable_encoder(payload))


@router.post("/{request_id}/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
async def send_heartbeat(
    request_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[
        LocalRuntimeAgentService, Depends(get_local_runtime_agent_service)
    ],
) -> None:
    try:
        await service.heartbeat(
            request_id=request_id, user_id=current_user.user_id.value
        )
    except LocalRuntimeWorkRequestNotClaimableError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e


@router.post("/{request_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
async def complete_work_request(
    request_id: str,
    request: LocalRuntimeCompleteRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[
        LocalRuntimeAgentService, Depends(get_local_runtime_agent_service)
    ],
) -> None:
    try:
        await service.complete(
            request_id=request_id,
            user_id=current_user.user_id.value,
            result=request.result,
        )
    except LocalRuntimeWorkRequestNotClaimableError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e


@router.post("/{request_id}/fail", status_code=status.HTTP_204_NO_CONTENT)
async def fail_work_request(
    request_id: str,
    request: LocalRuntimeFailRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[
        LocalRuntimeAgentService, Depends(get_local_runtime_agent_service)
    ],
) -> None:
    try:
        await service.fail(
            request_id=request_id,
            user_id=current_user.user_id.value,
            failure_reason=request.failure_reason,
        )
    except LocalRuntimeWorkRequestNotClaimableError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
