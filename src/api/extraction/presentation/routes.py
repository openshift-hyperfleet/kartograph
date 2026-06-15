"""HTTP routes for extraction session lifecycle operations."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from extraction.application import ExtractionAgentSessionService
from extraction.application.chat_turn_service import ExtractionChatTurnService
from extraction.dependencies import (
    get_extraction_agent_session_service,
    get_extraction_agent_session_service_with_runtime,
    get_extraction_chat_turn_service,
)
from extraction.domain.graph_management_session_scope import resolve_backend_session_mode
from extraction.domain.value_objects import ExtractionSessionMode, GraphManagementUiMode
from extraction.presentation.models import (
    BootstrapIntakePathSelectionRequest,
    ExtractionChatTurnRequest,
    ExtractionSessionHistoryItemResponse,
    ExtractionSessionHistoryResponse,
    ExtractionSessionListResponse,
    ExtractionSessionResponse,
    GraphManagementSessionRequest,
    StickyRuntimeWarmupRequest,
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

router = APIRouter(tags=["extraction-sessions"])

NDJSON_STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _validate_graph_management_session_mode(
    mode: ExtractionSessionMode,
    ui_mode: GraphManagementUiMode,
) -> None:
    if resolve_backend_session_mode(ui_mode) != mode:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="graph_management_ui_mode does not match session mode path",
        )


async def _assert_kg_edit_permission(
    *,
    authz: AuthorizationProvider,
    current_user: CurrentUser,
    knowledge_graph_id: str,
) -> None:
    subject = format_subject(ResourceType.USER, current_user.user_id.value)
    resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, knowledge_graph_id)
    allowed = await authz.check_permission(resource, Permission.EDIT, subject)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )


@router.get(
    "/knowledge-graphs/{knowledge_graph_id}/sessions/{mode}/active",
    response_model=ExtractionSessionResponse,
)
async def get_active_session(
    knowledge_graph_id: str,
    mode: ExtractionSessionMode,
    graph_management_ui_mode: GraphManagementUiMode,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[
        ExtractionAgentSessionService, Depends(get_extraction_agent_session_service_with_runtime)
    ],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
) -> ExtractionSessionResponse:
    await _assert_kg_edit_permission(
        authz=authz,
        current_user=current_user,
        knowledge_graph_id=knowledge_graph_id,
    )
    _validate_graph_management_session_mode(mode, graph_management_ui_mode)
    session = await service.get_active_session(
        user_id=current_user.user_id.value,
        knowledge_graph_id=knowledge_graph_id,
        ui_mode=graph_management_ui_mode,
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Graph Management Assistant session for this mode",
        )
    return ExtractionSessionResponse.from_domain(session)


@router.post(
    "/knowledge-graphs/{knowledge_graph_id}/sessions/{mode}/start-session",
    response_model=ExtractionSessionResponse,
)
async def start_session(
    knowledge_graph_id: str,
    mode: ExtractionSessionMode,
    request: GraphManagementSessionRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[
        ExtractionAgentSessionService, Depends(get_extraction_agent_session_service_with_runtime)
    ],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
) -> ExtractionSessionResponse:
    await _assert_kg_edit_permission(
        authz=authz,
        current_user=current_user,
        knowledge_graph_id=knowledge_graph_id,
    )
    _validate_graph_management_session_mode(mode, request.graph_management_ui_mode)
    session = await service.start_session(
        user_id=current_user.user_id.value,
        knowledge_graph_id=knowledge_graph_id,
        ui_mode=request.graph_management_ui_mode,
    )
    return ExtractionSessionResponse.from_domain(session)


@router.post(
    "/knowledge-graphs/{knowledge_graph_id}/sessions/{mode}/end-session",
    response_model=ExtractionSessionResponse,
)
async def end_session(
    knowledge_graph_id: str,
    mode: ExtractionSessionMode,
    request: GraphManagementSessionRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[
        ExtractionAgentSessionService,
        Depends(get_extraction_agent_session_service_with_runtime),
    ],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
) -> ExtractionSessionResponse:
    await _assert_kg_edit_permission(
        authz=authz,
        current_user=current_user,
        knowledge_graph_id=knowledge_graph_id,
    )
    _validate_graph_management_session_mode(mode, request.graph_management_ui_mode)
    session = await service.end_session(
        user_id=current_user.user_id.value,
        knowledge_graph_id=knowledge_graph_id,
        ui_mode=request.graph_management_ui_mode,
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Graph Management Assistant session for this mode",
        )
    return ExtractionSessionResponse.from_domain(session)


@router.get(
    "/knowledge-graphs/{knowledge_graph_id}/sessions/{mode}",
    response_model=ExtractionSessionListResponse,
)
async def list_sessions(
    knowledge_graph_id: str,
    mode: ExtractionSessionMode,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[
        ExtractionAgentSessionService, Depends(get_extraction_agent_session_service)
    ],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
) -> ExtractionSessionListResponse:
    await _assert_kg_edit_permission(
        authz=authz,
        current_user=current_user,
        knowledge_graph_id=knowledge_graph_id,
    )
    sessions = await service.list_sessions(
        user_id=current_user.user_id.value,
        knowledge_graph_id=knowledge_graph_id,
        mode=mode,
    )
    payload = [ExtractionSessionResponse.from_domain(session) for session in sessions]
    return ExtractionSessionListResponse(sessions=payload, count=len(payload))


@router.get(
    "/knowledge-graphs/{knowledge_graph_id}/sessions/{mode}/history",
    response_model=ExtractionSessionHistoryResponse,
)
async def list_session_history(
    knowledge_graph_id: str,
    mode: ExtractionSessionMode,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[
        ExtractionAgentSessionService, Depends(get_extraction_agent_session_service)
    ],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
) -> ExtractionSessionHistoryResponse:
    await _assert_kg_edit_permission(
        authz=authz,
        current_user=current_user,
        knowledge_graph_id=knowledge_graph_id,
    )
    history = await service.list_session_history(
        user_id=current_user.user_id.value,
        knowledge_graph_id=knowledge_graph_id,
        mode=mode,
    )
    payload = [
        ExtractionSessionHistoryItemResponse.from_history_record(record)
        for record in history
    ]
    return ExtractionSessionHistoryResponse(sessions=payload, count=len(payload))


@router.post(
    "/knowledge-graphs/{knowledge_graph_id}/sessions/{mode}/clear-chat",
    response_model=ExtractionSessionResponse,
)
async def clear_chat(
    knowledge_graph_id: str,
    mode: ExtractionSessionMode,
    request: GraphManagementSessionRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[
        ExtractionAgentSessionService,
        Depends(get_extraction_agent_session_service_with_runtime),
    ],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
) -> ExtractionSessionResponse:
    await _assert_kg_edit_permission(
        authz=authz,
        current_user=current_user,
        knowledge_graph_id=knowledge_graph_id,
    )
    _validate_graph_management_session_mode(mode, request.graph_management_ui_mode)
    session = await service.clear_chat(
        user_id=current_user.user_id.value,
        knowledge_graph_id=knowledge_graph_id,
        ui_mode=request.graph_management_ui_mode,
    )
    return ExtractionSessionResponse.from_domain(session)


@router.post(
    "/knowledge-graphs/{knowledge_graph_id}/sessions/{mode}/runtime/warm",
)
async def stream_runtime_warmup(
    knowledge_graph_id: str,
    mode: ExtractionSessionMode,
    request: StickyRuntimeWarmupRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ExtractionChatTurnService, Depends(get_extraction_chat_turn_service)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
) -> StreamingResponse:
    await _assert_kg_edit_permission(
        authz=authz,
        current_user=current_user,
        knowledge_graph_id=knowledge_graph_id,
    )
    _validate_graph_management_session_mode(mode, request.graph_management_ui_mode)

    async def event_stream():
        async for event in service.stream_runtime_warmup(
            user_id=current_user.user_id.value,
            tenant_id=current_user.tenant_id.value,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            ui_mode=request.graph_management_ui_mode,
        ):
            yield json.dumps(event) + "\n"
            await asyncio.sleep(0)

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers=NDJSON_STREAM_HEADERS,
    )


@router.post(
    "/knowledge-graphs/{knowledge_graph_id}/sessions/{mode}/chat",
)
async def stream_chat_turn(
    knowledge_graph_id: str,
    mode: ExtractionSessionMode,
    request: ExtractionChatTurnRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ExtractionChatTurnService, Depends(get_extraction_chat_turn_service)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
) -> StreamingResponse:
    await _assert_kg_edit_permission(
        authz=authz,
        current_user=current_user,
        knowledge_graph_id=knowledge_graph_id,
    )
    _validate_graph_management_session_mode(mode, request.graph_management_ui_mode)

    async def event_stream():
        async for event in service.stream_chat_turn(
            user_id=current_user.user_id.value,
            tenant_id=current_user.tenant_id.value,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            ui_mode=request.graph_management_ui_mode,
            message=request.message,
        ):
            yield json.dumps(event) + "\n"
            await asyncio.sleep(0)

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers=NDJSON_STREAM_HEADERS,
    )


@router.post(
    "/knowledge-graphs/{knowledge_graph_id}/sessions/schema_bootstrap/active/intake-path",
    response_model=ExtractionSessionResponse,
)
async def select_bootstrap_intake_path(
    knowledge_graph_id: str,
    request: BootstrapIntakePathSelectionRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[
        ExtractionAgentSessionService, Depends(get_extraction_agent_session_service)
    ],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
) -> ExtractionSessionResponse:
    await _assert_kg_edit_permission(
        authz=authz,
        current_user=current_user,
        knowledge_graph_id=knowledge_graph_id,
    )
    session = await service.set_bootstrap_intake_path_for_active_session(
        user_id=current_user.user_id.value,
        knowledge_graph_id=knowledge_graph_id,
        selected_path=request.selected_path,
        capabilities_goals=request.capabilities_goals,
    )
    return ExtractionSessionResponse.from_domain(session)

