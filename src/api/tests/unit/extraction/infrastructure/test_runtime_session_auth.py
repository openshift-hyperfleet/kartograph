"""Unit tests for sticky runtime session auth tokens."""

from __future__ import annotations

from extraction.infrastructure.runtime_session_auth import (
    RUNTIME_AUTH_HEADER,
    issue_runtime_auth_token,
    runtime_auth_matches,
)


def test_issue_runtime_auth_token_is_unique_and_non_empty() -> None:
    first = issue_runtime_auth_token()
    second = issue_runtime_auth_token()
    assert first
    assert second
    assert first != second


def test_runtime_auth_matches_rejects_missing_or_mismatched_values() -> None:
    token = issue_runtime_auth_token()
    assert runtime_auth_matches(expected=token, provided=token)
    assert not runtime_auth_matches(expected=token, provided="wrong")
    assert not runtime_auth_matches(expected="", provided=token)
    assert not runtime_auth_matches(expected=token, provided="")


def test_runtime_auth_header_constant() -> None:
    assert RUNTIME_AUTH_HEADER == "X-Kartograph-Runtime-Auth"
