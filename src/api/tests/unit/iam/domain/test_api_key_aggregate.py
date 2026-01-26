"""Unit tests for APIKey aggregate (TDD - tests first).

Following TDD: Write tests that describe the desired behavior,
then implement the APIKey aggregate to make these tests pass.
"""

from datetime import UTC, datetime, timedelta

import pytest

from iam.domain.aggregates import APIKey
from iam.domain.events import APIKeyCreated, APIKeyRevoked
from iam.domain.value_objects import APIKeyId, TenantId, UserId
from iam.ports.exceptions import APIKeyAlreadyRevokedError


class TestAPIKeyCreation:
    """Tests for APIKey aggregate creation via factory method."""

    def test_creates_with_required_fields(self):
        """Test that APIKey can be created with required fields."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()
        key_hash = "hashed_secret_value"
        prefix = "karto_ab"

        expires_at = datetime.now(UTC) + timedelta(days=1)

        api_key = APIKey.create(
            created_by_user_id=created_by_user_id,
            expires_at=expires_at,
            tenant_id=tenant_id,
            name="CI Pipeline Key",
            key_hash=key_hash,
            prefix=prefix,
        )

        assert api_key.created_by_user_id == created_by_user_id
        assert api_key.tenant_id == tenant_id
        assert api_key.name == "CI Pipeline Key"
        assert api_key.key_hash == key_hash
        assert api_key.prefix == prefix
        assert api_key.expires_at == expires_at
        assert api_key.last_used_at is None

    def test_factory_generates_ulid(self):
        """Factory should generate a ULID-based ID for the API key."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        api_key = APIKey.create(
            created_by_user_id=created_by_user_id,
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            tenant_id=tenant_id,
            name="Test Key",
            key_hash="hash",
            prefix="karto_ab",
        )

        assert api_key.id is not None
        assert isinstance(api_key.id, APIKeyId)
        assert len(api_key.id.value) == 26  # ULID length

    def test_factory_stores_prefix(self):
        """Factory should store the provided prefix for key identification."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()
        prefix = "karto_xy"

        api_key = APIKey.create(
            created_by_user_id=created_by_user_id,
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            tenant_id=tenant_id,
            name="Test Key",
            key_hash="hash",
            prefix=prefix,
        )

        assert api_key.prefix == prefix

    def test_factory_records_created_event(self):
        """Factory should record an APIKeyCreated event."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        api_key = APIKey.create(
            created_by_user_id=created_by_user_id,
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            tenant_id=tenant_id,
            name="Test Key",
            key_hash="hash",
            prefix="karto_ab",
        )
        events = api_key.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], APIKeyCreated)
        assert events[0].api_key_id == api_key.id.value
        # Events still use user_id - this is the creator for SpiceDB authorization
        assert events[0].user_id == created_by_user_id.value
        assert events[0].tenant_id == tenant_id.value
        assert events[0].name == "Test Key"
        assert events[0].prefix == "karto_ab"

    def test_created_key_is_not_revoked(self):
        """A newly created API key should not be revoked."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        api_key = APIKey.create(
            created_by_user_id=created_by_user_id,
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            tenant_id=tenant_id,
            name="Test Key",
            key_hash="hash",
            prefix="karto_ab",
        )

        assert api_key.is_revoked is False

    def test_creates_with_expiration(self):
        """Test that APIKey can be created with an expiration date."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()
        expires_at = datetime.now(UTC) + timedelta(days=30)

        api_key = APIKey.create(
            created_by_user_id=created_by_user_id,
            tenant_id=tenant_id,
            name="Expiring Key",
            key_hash="hash",
            prefix="karto_ab",
            expires_at=expires_at,
        )

        assert api_key.expires_at == expires_at


class TestAPIKeyRevocation:
    """Tests for APIKey.revoke() business logic."""

    def test_revoke_marks_key_as_revoked(self):
        """Test that revoke() marks the key as revoked."""
        api_key = APIKey.create(
            created_by_user_id=UserId.generate(),
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            tenant_id=TenantId.generate(),
            name="Test Key",
            key_hash="hash",
            prefix="karto_ab",
        )
        api_key.collect_events()  # Clear creation event

        api_key.revoke()

        assert api_key.is_revoked is True

    def test_revoke_records_event(self):
        """Test that revoke() records an APIKeyRevoked event."""
        created_by_user_id = UserId.generate()
        api_key = APIKey.create(
            created_by_user_id=created_by_user_id,
            tenant_id=TenantId.generate(),
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            name="Test Key",
            key_hash="hash",
            prefix="karto_ab",
        )
        api_key.collect_events()  # Clear creation event

        api_key.revoke()
        events = api_key.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], APIKeyRevoked)
        assert events[0].api_key_id == api_key.id.value
        # Events still use user_id - this is the creator for SpiceDB authorization
        assert events[0].user_id == created_by_user_id.value

    def test_revoke_already_revoked_raises_error(self):
        """Test that revoking an already-revoked key raises APIKeyAlreadyRevokedError."""
        api_key = APIKey.create(
            created_by_user_id=UserId.generate(),
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            tenant_id=TenantId.generate(),
            name="Test Key",
            key_hash="hash",
            prefix="karto_ab",
        )
        api_key.revoke()

        with pytest.raises(APIKeyAlreadyRevokedError):
            api_key.revoke()


class TestAPIKeyValidity:
    """Tests for APIKey.is_valid() method."""

    def test_valid_key_returns_true(self):
        """Test that a valid key returns True from is_valid()."""
        api_key = APIKey.create(
            created_by_user_id=UserId.generate(),
            tenant_id=TenantId.generate(),
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            name="Test Key",
            key_hash="hash",
            prefix="karto_ab",
        )

        assert api_key.is_valid() is True

    def test_revoked_key_returns_false(self):
        """Test that a revoked key returns False from is_valid()."""
        api_key = APIKey.create(
            created_by_user_id=UserId.generate(),
            tenant_id=TenantId.generate(),
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            name="Test Key",
            key_hash="hash",
            prefix="karto_ab",
        )
        api_key.revoke()

        assert api_key.is_valid() is False

    def test_expired_key_returns_false(self):
        """Test that an expired key returns False from is_valid()."""
        api_key = APIKey.create(
            created_by_user_id=UserId.generate(),
            tenant_id=TenantId.generate(),
            name="Test Key",
            key_hash="hash",
            prefix="karto_ab",
            expires_at=datetime.now(UTC) - timedelta(hours=1),  # Already expired
        )

        assert api_key.is_valid() is False

    def test_non_expired_key_returns_true(self):
        """Test that a key with future expiration returns True from is_valid()."""
        api_key = APIKey.create(
            created_by_user_id=UserId.generate(),
            tenant_id=TenantId.generate(),
            name="Test Key",
            key_hash="hash",
            prefix="karto_ab",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )

        assert api_key.is_valid() is True


class TestAPIKeyUsageTracking:
    """Tests for APIKey.record_usage() method."""

    def test_record_usage_updates_last_used_at(self):
        """Test that record_usage() updates last_used_at timestamp."""
        api_key = APIKey.create(
            created_by_user_id=UserId.generate(),
            tenant_id=TenantId.generate(),
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            name="Test Key",
            key_hash="hash",
            prefix="karto_ab",
        )
        assert api_key.last_used_at is None

        before = datetime.now(UTC)
        api_key.record_usage()
        after = datetime.now(UTC)

        assert api_key.last_used_at is not None
        assert before <= api_key.last_used_at <= after


class TestAPIKeyEventCollection:
    """Tests for APIKey event collection mechanism."""

    def test_collect_events_returns_empty_list_after_collection(self):
        """Test that collect_events clears the pending events list."""
        api_key = APIKey.create(
            created_by_user_id=UserId.generate(),
            tenant_id=TenantId.generate(),
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            name="Test Key",
            key_hash="hash",
            prefix="karto_ab",
        )

        # First collection should have the created event
        events1 = api_key.collect_events()
        assert len(events1) == 1

        # Second collection should be empty
        events2 = api_key.collect_events()
        assert events2 == []

    def test_multiple_operations_record_multiple_events(self):
        """Test that multiple operations record multiple events."""
        api_key = APIKey.create(
            created_by_user_id=UserId.generate(),
            tenant_id=TenantId.generate(),
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            name="Test Key",
            key_hash="hash",
            prefix="karto_ab",
        )
        api_key.revoke()

        events = api_key.collect_events()

        assert len(events) == 2
        assert isinstance(events[0], APIKeyCreated)
        assert isinstance(events[1], APIKeyRevoked)
