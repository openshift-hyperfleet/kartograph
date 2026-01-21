"""Tests for authentication fixtures.

These tests verify that the Keycloak integration fixtures work correctly.
Requires a running Keycloak instance with the kartograph realm configured.
"""

import pytest
from jose import jwt

pytestmark = pytest.mark.integration


class TestAuthFixtures:
    """Tests for authentication fixtures."""

    def test_get_test_token_returns_valid_jwt(self, get_test_token):
        """Should return a valid JWT from Keycloak."""
        token = get_test_token("alice", "password")

        # Decode without verification to check structure
        claims = jwt.get_unverified_claims(token)

        assert claims["preferred_username"] == "alice"
        assert "sub" in claims
        assert claims["iss"] == "http://localhost:8080/realms/kartograph"

    def test_get_test_token_with_bob(self, get_test_token):
        """Should return a valid JWT for bob user."""
        token = get_test_token("bob", "password")

        claims = jwt.get_unverified_claims(token)

        assert claims["preferred_username"] == "bob"
        assert "sub" in claims

    def test_get_test_token_invalid_credentials_raises(self, get_test_token):
        """Should raise an error for invalid credentials."""
        import httpx

        with pytest.raises(httpx.HTTPStatusError):
            get_test_token("alice", "wrong-password")

    def test_alice_token_fixture(self, alice_token):
        """Should provide alice's token directly."""
        claims = jwt.get_unverified_claims(alice_token)
        assert claims["preferred_username"] == "alice"

    def test_bob_token_fixture(self, bob_token):
        """Should provide bob's token directly."""
        claims = jwt.get_unverified_claims(bob_token)
        assert claims["preferred_username"] == "bob"

    def test_auth_headers_fixture(self, auth_headers):
        """Should provide properly formatted auth headers."""
        assert "Authorization" in auth_headers
        assert auth_headers["Authorization"].startswith("Bearer ")

    def test_tokens_contain_email_claim(self, alice_token, bob_token):
        """Should include email claim in tokens."""
        alice_claims = jwt.get_unverified_claims(alice_token)
        bob_claims = jwt.get_unverified_claims(bob_token)

        assert alice_claims.get("email") == "alice@example.com"
        assert bob_claims.get("email") == "bob@example.com"
