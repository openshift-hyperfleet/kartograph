"""FastAPI dependency helpers for extraction workload token authentication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from extraction.infrastructure.workload_runtime import ScopedWorkloadCredentialIssuer
from extraction.ports.runtime import ScopedWorkloadCredentials
from infrastructure.extraction_workload.dependencies import (
    get_extraction_workload_credential_issuer,
)


@dataclass(frozen=True)
class WorkloadAuthContext:
    """Authenticated workload context derived from a runtime token."""

    credentials: ScopedWorkloadCredentials
    tenant_id: str
    knowledge_graph_id: str
    session_id: str | None = None


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

    tenant_scope = next(
        (scope.removeprefix("tenant:") for scope in credentials.scopes if scope.startswith("tenant:")),
        None,
    )
    kg_scope = next(
        (
            scope.removeprefix("knowledge_graph:")
            for scope in credentials.scopes
            if scope.startswith("knowledge_graph:")
        ),
        None,
    )
    if not tenant_scope or not kg_scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workload token is missing tenant or knowledge graph scope",
        )

    session_scope = next(
        (scope.removeprefix("session:") for scope in credentials.scopes if scope.startswith("session:")),
        None,
    )

    return WorkloadAuthContext(
        credentials=credentials,
        tenant_id=tenant_scope,
        knowledge_graph_id=kg_scope,
        session_id=session_scope,
    )
