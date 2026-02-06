"""Unit tests for SpiceDB client input validation."""

import pytest

from shared_kernel.authorization.spicedb.client import SpiceDBClient


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
