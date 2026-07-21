"""Unit tests for the OpenShell CLI subprocess wrapper's secret redaction."""

from __future__ import annotations

from extraction.infrastructure.openshell.cli import redact_args


def test_redact_args_masks_vertex_service_account_token() -> None:
    args = [
        "provider",
        "update",
        "--credential",
        "VERTEX_AI_SERVICE_ACCOUNT_TOKEN=super-secret-token",
        "kartograph-gma",
    ]

    redacted = redact_args(args)

    assert "VERTEX_AI_SERVICE_ACCOUNT_TOKEN=<redacted>" in redacted
    assert "super-secret-token" not in " ".join(redacted)


def test_redact_args_leaves_non_secret_args_untouched() -> None:
    args = ["sandbox", "get", "kartograph-gma-sess-1"]

    assert redact_args(args) == args
