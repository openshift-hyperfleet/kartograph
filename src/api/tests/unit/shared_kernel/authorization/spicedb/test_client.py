"""Unit tests for SpiceDB client input validation."""

import pytest

from shared_kernel.authorization.spicedb.client import (
    SpiceDBClient,
    _build_relationship_update,
    _parse_reference,
    _parse_subject_reference,
    RelationshipOperation,
)


class TestParseReference:
    """Tests for _parse_reference helper function."""

    def test_parses_simple_reference(self):
        """Should parse 'type:id' into (type, id)."""
        result = _parse_reference("user:alice", "subject")
        assert result == ("user", "alice")

    def test_raises_on_missing_colon(self):
        """Should raise ValueError if no colon separator."""
        with pytest.raises(ValueError, match="Invalid subject format"):
            _parse_reference("user_alice", "subject")


class TestParseSubjectReference:
    """Tests for _parse_subject_reference helper function."""

    def test_parses_subject_without_relation(self):
        """Should parse 'type:id' into (type, id, None)."""
        obj_type, obj_id, relation = _parse_subject_reference("user:alice")
        assert obj_type == "user"
        assert obj_id == "alice"
        assert relation is None

    def test_parses_subject_with_relation(self):
        """Should parse 'type:id#relation' into (type, id, relation)."""
        obj_type, obj_id, relation = _parse_subject_reference("group:eng-team#member")
        assert obj_type == "group"
        assert obj_id == "eng-team"
        assert relation == "member"

    def test_raises_on_missing_colon(self):
        """Should raise ValueError if no colon separator."""
        with pytest.raises(ValueError, match="Invalid subject format"):
            _parse_subject_reference("user_alice")


class TestBuildRelationshipUpdateSubjectRelation:
    """Tests for _build_relationship_update with subject relations."""

    def test_builds_update_without_subject_relation(self):
        """Subject without #relation should produce SubjectReference without optional_relation."""
        update = _build_relationship_update(
            resource="workspace:ws1",
            relation="admin",
            subject="user:alice",
            operation=RelationshipOperation.WRITE,
        )
        subject_ref = update.relationship.subject
        assert subject_ref.object.object_type == "user"
        assert subject_ref.object.object_id == "alice"
        assert subject_ref.optional_relation == ""

    def test_builds_update_with_subject_relation(self):
        """Subject with #relation should produce SubjectReference with optional_relation."""
        update = _build_relationship_update(
            resource="workspace:ws1",
            relation="admin",
            subject="group:eng-team#member",
            operation=RelationshipOperation.WRITE,
        )
        subject_ref = update.relationship.subject
        assert subject_ref.object.object_type == "group"
        assert subject_ref.object.object_id == "eng-team"
        assert subject_ref.optional_relation == "member"


class TestDeleteRelationshipsByFilterValidation:
    """Tests for delete_relationships_by_filter input validation."""

    @pytest.fixture
    def client(self) -> SpiceDBClient:
        """Create a SpiceDBClient instance for testing (no real connection needed)."""
        return SpiceDBClient(
            endpoint="localhost:50051",
            preshared_key="test_key",
            use_tls=False,
        )

    @pytest.mark.asyncio
    async def test_raises_error_when_no_filter_params_provided(
        self, client: SpiceDBClient
    ):
        """Test that at least one filter parameter beyond resource_type is required."""
        with pytest.raises(
            ValueError,
            match="At least one filter parameter beyond resource_type must be specified",
        ):
            await client.delete_relationships_by_filter(
                resource_type="workspace",
            )

    @pytest.mark.asyncio
    async def test_raises_error_when_subject_id_provided_without_subject_type(
        self, client: SpiceDBClient
    ):
        """Test that subject_id without subject_type raises ValueError."""
        with pytest.raises(
            ValueError,
            match="subject_type must be provided when subject_id is specified",
        ):
            await client.delete_relationships_by_filter(
                resource_type="workspace",
                resource_id="123",
                subject_id="abc",
            )


class TestReadRelationshipsValidation:
    """Tests for read_relationships input validation."""

    @pytest.fixture
    def client(self) -> SpiceDBClient:
        """Create a SpiceDBClient instance for testing (no real connection needed)."""
        return SpiceDBClient(
            endpoint="localhost:50051",
            preshared_key="test_key",
            use_tls=False,
        )

    @pytest.mark.asyncio
    async def test_raises_error_when_subject_id_provided_without_subject_type(
        self, client: SpiceDBClient
    ):
        """Test that subject_id without subject_type raises ValueError."""
        with pytest.raises(
            ValueError,
            match="subject_type must be provided when subject_id is specified",
        ):
            await client.read_relationships(
                resource_type="workspace",
                resource_id="123",
                subject_id="abc",
            )
