"""FastAPI dependency helpers for extraction workload token authentication."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from extraction.infrastructure.workload_credential_issuer import (
    WORKLOAD_SCOPE_ADMIN,
    WORKLOAD_SCOPE_CHAT,
    WORKLOAD_SCOPE_READ,
    WORKLOAD_SCOPE_WRITE,
)
from extraction.infrastructure.workload_runtime import ScopedWorkloadCredentialIssuer
from extraction.ports.runtime import ScopedWorkloadCredentials
from infrastructure.extraction_workload.dependencies import (
    get_extraction_workload_credential_issuer,
)

_WORKLOAD_SCOPE_ID = re.compile(r"^[0-9A-Za-z_-]+$")

_READ_SCOPES = frozenset(
    {
        WORKLOAD_SCOPE_CHAT,
        WORKLOAD_SCOPE_READ,
        WORKLOAD_SCOPE_WRITE,
        WORKLOAD_SCOPE_ADMIN,
    }
)
_WRITE_SCOPES = frozenset(
    {
        WORKLOAD_SCOPE_CHAT,
        WORKLOAD_SCOPE_WRITE,
        WORKLOAD_SCOPE_ADMIN,
    }
)
_ADMIN_SCOPES = frozenset({WORKLOAD_SCOPE_CHAT, WORKLOAD_SCOPE_ADMIN})


def _require_any_scope(auth: WorkloadAuthContext, allowed: frozenset[str], *, detail: str) -> None:
    if not allowed.intersection(auth.credentials.scopes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def require_workload_read_scope(auth: WorkloadAuthContext) -> None:
    _require_any_scope(
        auth,
        _READ_SCOPES,
        detail="Workload token is not authorized for read-only graph operations",
    )


def require_workload_write_scope(auth: WorkloadAuthContext) -> None:
    _require_any_scope(
        auth,
        _WRITE_SCOPES,
        detail="Workload token is not authorized for graph mutation writes",
    )


def require_workload_admin_scope(auth: WorkloadAuthContext) -> None:
    _require_any_scope(
        auth,
        _ADMIN_SCOPES,
        detail="Workload token is not authorized for schema or job configuration changes",
    )


def validate_workload_scope_id(value: str, *, field: str) -> str:
    """Reject scope-derived identifiers with unsafe characters."""
    if not value or _WORKLOAD_SCOPE_ID.fullmatch(value) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Workload token has invalid {field} scope",
        )
    return value


def _extract_scoped_value(scopes: tuple[str, ...], prefix: str) -> str | None:
    for scope in scopes:
        if scope.startswith(prefix):
            return scope.removeprefix(prefix)
    return None


@dataclass(frozen=True)
class WorkloadAuthContext:
    """Authenticated workload context derived from a runtime token."""

    credentials: ScopedWorkloadCredentials
    tenant_id: str
    knowledge_graph_id: str
    session_id: str | None = None
    job_id: str | None = None


def get_workload_auth_context(
    workload_token: Annotated[str | None, Header(alias="X-Workload-Token")] = None,
    issuer: Annotated[
        ScopedWorkloadCredentialIssuer, Depends(get_extraction_workload_credential_issuer)
    ] = ...,
) -> WorkloadAuthContext:
    """Validate a sticky-session or worker runtime token."""
    if not workload_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Workload-Token header",
        )

    credentials = issuer.verify(workload_token)
    if credentials is None or credentials.expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired workload token",
        )

    tenant_scope = _extract_scoped_value(credentials.scopes, "tenant:")
    kg_scope = _extract_scoped_value(credentials.scopes, "knowledge_graph:")
    if not tenant_scope or not kg_scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workload token is missing tenant or knowledge graph scope",
        )

    tenant_id = validate_workload_scope_id(tenant_scope, field="tenant")
    knowledge_graph_id = validate_workload_scope_id(kg_scope, field="knowledge_graph")

    session_scope = _extract_scoped_value(credentials.scopes, "session:")
    job_scope = _extract_scoped_value(credentials.scopes, "job:")
    session_id = (
        validate_workload_scope_id(session_scope, field="session")
        if session_scope is not None
        else None
    )
    job_id = (
        validate_workload_scope_id(job_scope, field="job") if job_scope is not None else None
    )

    return WorkloadAuthContext(
        credentials=credentials,
        tenant_id=tenant_id,
        knowledge_graph_id=knowledge_graph_id,
        session_id=session_id,
        job_id=job_id,
    )
