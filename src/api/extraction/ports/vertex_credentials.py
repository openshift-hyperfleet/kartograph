"""Port contract for minting short-lived Vertex AI tokens for local agents.

See specs/extraction/local-sandbox-execution.spec.md, "Downscoped, Short-Lived
Vertex Credential Injection". Distinct from `workload_credential_issuer.py`,
which mints Kartograph-internal JWTs for sandbox-to-API callbacks -- this port
mints external Google Cloud credentials for the Sandbox's own outbound Vertex
AI inference calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class VertexInferenceToken:
    """A short-lived Google Cloud access token restricted to Vertex AI use."""

    access_token: str = field(repr=False)
    expires_at: datetime


class VertexInferenceTokenUnavailableError(RuntimeError):
    """Raised when local-agent Vertex token minting is not configured or fails."""


class IVertexInferenceTokenIssuer(Protocol):
    """Mints a Vertex-AI-scoped access token for injection into a local Sandbox."""

    def mint_token(
        self, *, tenant_id: str, knowledge_graph_id: str, session_id: str
    ) -> VertexInferenceToken: ...
