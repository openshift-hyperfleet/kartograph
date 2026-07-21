"""Mints short-lived, impersonation-restricted Vertex AI tokens for local agents.

See specs/extraction/local-sandbox-execution.spec.md, "Downscoped, Short-Lived
Vertex Credential Injection". Google Cloud's Credential Access Boundary (CAB)
feature only restricts tokens for Cloud Storage resources -- it cannot scope a
token to Vertex AI. The equivalent, GCP-supported mechanism for restricting a
token to Vertex-AI-only permissions is impersonating a dedicated, minimally-
privileged service account (granted only Vertex AI roles, provisioned out of
band, e.g. `roles/aiplatform.user`) via the IAM Credentials API, with an
explicit short lifetime. The impersonated service account's private key
material never leaves Google's systems -- `google.auth.impersonated_credentials`
never generates, holds, or transmits key material; it exchanges the caller's
own credentials for a short-lived access token scoped to the target principal.
"""

from __future__ import annotations

from datetime import UTC, datetime

import google.auth
from google.auth import impersonated_credentials
from google.auth.transport.requests import Request as GoogleAuthRequest

from extraction.ports.vertex_credentials import (
    VertexInferenceToken,
    VertexInferenceTokenUnavailableError,
)

_VERTEX_AI_SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class ImpersonatedVertexInferenceTokenIssuer:
    """Impersonates a Vertex-AI-only service account to mint short-lived tokens.

    Disabled (raises `VertexInferenceTokenUnavailableError` on mint) when no
    `service_account_email` is configured, so environments that never enable
    local execution mode never attempt Google Cloud calls.
    """

    def __init__(
        self,
        *,
        service_account_email: str,
        lifetime_seconds: int,
        source_credentials_path: str | None = None,
    ) -> None:
        self._service_account_email = service_account_email.strip()
        self._lifetime_seconds = lifetime_seconds
        self._source_credentials_path = source_credentials_path

    def mint_token(
        self, *, tenant_id: str, knowledge_graph_id: str, session_id: str
    ) -> VertexInferenceToken:
        if not self._service_account_email:
            raise VertexInferenceTokenUnavailableError(
                "Local agent Vertex token minting is not configured "
                "(vertex_local_agent_service_account_email is unset)."
            )
        try:
            source_credentials = self._load_source_credentials()
            target_credentials = impersonated_credentials.Credentials(
                source_credentials=source_credentials,
                target_principal=self._service_account_email,
                target_scopes=list(_VERTEX_AI_SCOPES),
                lifetime=self._lifetime_seconds,
            )
            target_credentials.refresh(GoogleAuthRequest())
        except VertexInferenceTokenUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface as a domain-meaningful error
            raise VertexInferenceTokenUnavailableError(
                "Failed to mint an impersonated Vertex AI access token for "
                f"{self._service_account_email!r}: {exc}"
            ) from exc

        if not target_credentials.token or target_credentials.expiry is None:
            raise VertexInferenceTokenUnavailableError(
                "Google Cloud IAM Credentials API returned no access token "
                f"when impersonating {self._service_account_email!r}."
            )
        return VertexInferenceToken(
            access_token=target_credentials.token,
            expires_at=_ensure_utc(target_credentials.expiry),
        )

    def _load_source_credentials(self):  # noqa: ANN202 - google-auth Credentials
        if self._source_credentials_path:
            credentials, _ = google.auth.load_credentials_from_file(
                self._source_credentials_path,
                scopes=list(_VERTEX_AI_SCOPES),
            )
            return credentials
        credentials, _ = google.auth.default(scopes=list(_VERTEX_AI_SCOPES))
        return credentials
