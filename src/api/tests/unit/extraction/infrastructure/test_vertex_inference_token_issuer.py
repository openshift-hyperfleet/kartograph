"""Unit tests for the local-agent Vertex AI token issuer.

See specs/extraction/local-sandbox-execution.spec.md, "Downscoped, Short-Lived
Vertex Credential Injection".
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from extraction.infrastructure.vertex_inference_token_issuer import (
    ImpersonatedVertexInferenceTokenIssuer,
)
from extraction.ports.vertex_credentials import VertexInferenceTokenUnavailableError


def test_mint_token_raises_when_service_account_email_unset() -> None:
    issuer = ImpersonatedVertexInferenceTokenIssuer(
        service_account_email="", lifetime_seconds=900
    )

    with pytest.raises(VertexInferenceTokenUnavailableError, match="not configured"):
        issuer.mint_token(
            tenant_id="tenant-1", knowledge_graph_id="kg-1", session_id="sess-1"
        )


def test_mint_token_impersonates_configured_service_account() -> None:
    issuer = ImpersonatedVertexInferenceTokenIssuer(
        service_account_email="vertex-inference@proj.iam.gserviceaccount.com",
        lifetime_seconds=900,
        source_credentials_path="/gcloud/config/application_default_credentials.json",
    )
    fake_source_creds = MagicMock()
    expiry = datetime(2026, 1, 1, 12, 0, 0)

    def _fake_refresh(request: object) -> None:
        target_credentials.token = "minted-access-token"
        target_credentials.expiry = expiry

    target_credentials = MagicMock()
    target_credentials.token = None
    target_credentials.expiry = None
    target_credentials.refresh.side_effect = _fake_refresh

    with (
        patch(
            "extraction.infrastructure.vertex_inference_token_issuer.google.auth.load_credentials_from_file",
            return_value=(fake_source_creds, "proj"),
        ) as load_from_file,
        patch(
            "extraction.infrastructure.vertex_inference_token_issuer.impersonated_credentials.Credentials",
            return_value=target_credentials,
        ) as impersonated_ctor,
    ):
        token = issuer.mint_token(
            tenant_id="tenant-1", knowledge_graph_id="kg-1", session_id="sess-1"
        )

    load_from_file.assert_called_once_with(
        "/gcloud/config/application_default_credentials.json",
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    impersonated_ctor.assert_called_once_with(
        source_credentials=fake_source_creds,
        target_principal="vertex-inference@proj.iam.gserviceaccount.com",
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
        lifetime=900,
    )
    assert token.access_token == "minted-access-token"
    assert token.expires_at == expiry.replace(tzinfo=UTC)


def test_mint_token_falls_back_to_ambient_adc_when_no_path_configured() -> None:
    issuer = ImpersonatedVertexInferenceTokenIssuer(
        service_account_email="vertex-inference@proj.iam.gserviceaccount.com",
        lifetime_seconds=900,
        source_credentials_path=None,
    )
    fake_source_creds = MagicMock()
    target_credentials = MagicMock()
    target_credentials.token = "tok"
    target_credentials.expiry = datetime.now(UTC) + timedelta(minutes=15)

    with (
        patch(
            "extraction.infrastructure.vertex_inference_token_issuer.google.auth.default",
            return_value=(fake_source_creds, "proj"),
        ) as default_creds,
        patch(
            "extraction.infrastructure.vertex_inference_token_issuer.impersonated_credentials.Credentials",
            return_value=target_credentials,
        ),
    ):
        issuer.mint_token(
            tenant_id="tenant-1", knowledge_graph_id="kg-1", session_id="sess-1"
        )

    default_creds.assert_called_once_with(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )


def test_mint_token_wraps_underlying_errors() -> None:
    issuer = ImpersonatedVertexInferenceTokenIssuer(
        service_account_email="vertex-inference@proj.iam.gserviceaccount.com",
        lifetime_seconds=900,
    )

    with patch(
        "extraction.infrastructure.vertex_inference_token_issuer.google.auth.default",
        side_effect=RuntimeError("no ADC found"),
    ):
        with pytest.raises(VertexInferenceTokenUnavailableError, match="no ADC found"):
            issuer.mint_token(
                tenant_id="tenant-1", knowledge_graph_id="kg-1", session_id="sess-1"
            )


def test_mint_token_raises_when_no_token_returned() -> None:
    issuer = ImpersonatedVertexInferenceTokenIssuer(
        service_account_email="vertex-inference@proj.iam.gserviceaccount.com",
        lifetime_seconds=900,
    )
    fake_source_creds = MagicMock()
    target_credentials = MagicMock()
    target_credentials.token = None
    target_credentials.expiry = None

    with (
        patch(
            "extraction.infrastructure.vertex_inference_token_issuer.google.auth.default",
            return_value=(fake_source_creds, "proj"),
        ),
        patch(
            "extraction.infrastructure.vertex_inference_token_issuer.impersonated_credentials.Credentials",
            return_value=target_credentials,
        ),
    ):
        with pytest.raises(
            VertexInferenceTokenUnavailableError, match="no access token"
        ):
            issuer.mint_token(
                tenant_id="tenant-1", knowledge_graph_id="kg-1", session_id="sess-1"
            )
