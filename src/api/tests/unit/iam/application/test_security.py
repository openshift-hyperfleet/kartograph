"""Unit tests for API key security utilities.

Following TDD - these tests define the expected behavior for API key
secret generation, hashing, and verification.

Note: Test strings in this file are synthetic test data, not real secrets.
"""
# gitleaks:allow


class TestAPIKeySecretGeneration:
    """Tests for generate_api_key_secret function."""

    def test_generates_url_safe_token(self):
        """Generated secret should be URL-safe (no special characters)."""
        from iam.application.security import generate_api_key_secret

        secret = generate_api_key_secret()

        # URL-safe means only alphanumeric, dash, and underscore
        # After removing the karto_ prefix, check the random part
        random_part = secret.removeprefix("karto_")
        allowed_chars = set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        )
        assert all(c in allowed_chars for c in random_part)

    def test_has_karto_prefix(self):
        """Generated secret should have karto_ prefix for identification."""
        from iam.application.security import generate_api_key_secret

        secret = generate_api_key_secret()

        assert secret.startswith("karto_")

    def test_generates_unique_secrets(self):
        """Each generated secret should be unique."""
        from iam.application.security import generate_api_key_secret

        secrets = [generate_api_key_secret() for _ in range(100)]

        assert len(secrets) == len(set(secrets))

    def test_generates_sufficient_entropy(self):
        """Generated secret should have at least 32 bytes of entropy."""
        from iam.application.security import generate_api_key_secret

        secret = generate_api_key_secret()

        # Remove karto_ prefix (6 chars)
        random_part = secret[6:]
        # Base64-URL encoded 32 bytes = ~43 characters
        # token_urlsafe(32) produces 43 characters
        assert len(random_part) >= 43


class TestExtractPrefix:
    """Tests for extract_prefix function."""

    def test_extracts_first_12_characters(self):
        """Should extract first 12 characters as prefix."""
        from iam.application.security import extract_prefix

        secret = "karto_abc123def456xyz789"  # gitleaks:allow
        prefix = extract_prefix(secret)

        assert prefix == "karto_abc123"
        assert len(prefix) == 12

    def test_handles_short_secrets(self):
        """Should handle secrets shorter than 12 characters."""
        from iam.application.security import extract_prefix

        short_secret = "short"
        prefix = extract_prefix(short_secret)

        assert prefix == "short"


class TestAPIKeyHashing:
    """Tests for hash_api_key_secret and verify_api_key_secret functions."""

    def test_hashes_secret(self):
        """Should produce a hash from a secret."""
        from iam.application.security import hash_api_key_secret

        secret = "karto_abcdef"  # gitleaks:allow
        key_hash = hash_api_key_secret(secret)

        assert key_hash is not None
        assert isinstance(key_hash, str)
        assert len(key_hash) > 0

    def test_verifies_correct_secret(self):
        """Should verify correct secret against its hash."""
        from iam.application.security import (
            hash_api_key_secret,
            verify_api_key_secret,
        )

        secret = "karto_abcdef"  # gitleaks:allow
        key_hash = hash_api_key_secret(secret)

        assert verify_api_key_secret(secret, key_hash) is True

    def test_rejects_incorrect_secret(self):
        """Should reject incorrect secret."""
        from iam.application.security import (
            hash_api_key_secret,
            verify_api_key_secret,
        )

        secret = "karto_correct"  # gitleaks:allow
        wrong_secret = "karto_wrong"  # gitleaks:allow
        key_hash = hash_api_key_secret(secret)

        assert verify_api_key_secret(wrong_secret, key_hash) is False

    def test_hash_is_different_from_plaintext(self):
        """Hash should not be the same as the plaintext secret."""
        from iam.application.security import hash_api_key_secret

        secret = "karto_abcdef"  # gitleaks:allow
        key_hash = hash_api_key_secret(secret)

        assert key_hash != secret

    def test_same_secret_produces_different_hashes(self):
        """Hashing same secret twice should produce different hashes (salt)."""
        from iam.application.security import hash_api_key_secret

        secret = "karto_abcdef"  # gitleaks:allow
        hash1 = hash_api_key_secret(secret)
        hash2 = hash_api_key_secret(secret)

        # bcrypt uses random salt, so hashes should differ
        assert hash1 != hash2

    def test_handles_invalid_hash_format(self):
        """Should return False for invalid hash format, not raise."""
        from iam.application.security import verify_api_key_secret

        secret = "karto_test"  # gitleaks:allow
        invalid_hash = "not_a_valid_bcrypt_hash"

        # Should return False, not raise an exception
        assert verify_api_key_secret(secret, invalid_hash) is False
