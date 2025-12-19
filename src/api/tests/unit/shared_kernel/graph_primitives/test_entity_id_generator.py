"""Tests for EntityIdGenerator.

This module tests the deterministic entity ID generation logic that is shared
across bounded contexts (particularly Graph and Extraction contexts).
"""

import pytest


class TestEntityIdGenerator:
    """Test suite for EntityIdGenerator.generate method."""

    def test_is_deterministic(self):
        """Same inputs should produce same ID."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        id1 = EntityIdGenerator.generate("person", "alice-smith")
        id2 = EntityIdGenerator.generate("person", "alice-smith")
        assert id1 == id2

    def test_includes_type_prefix(self):
        """Generated ID should include entity type as prefix."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        id_value = EntityIdGenerator.generate("person", "alice-smith")
        assert id_value.startswith("person:")

    def test_different_for_different_slugs(self):
        """Different slugs should produce different IDs."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        id1 = EntityIdGenerator.generate("person", "alice-smith")
        id2 = EntityIdGenerator.generate("person", "bob-jones")
        assert id1 != id2

    def test_different_for_different_types(self):
        """Different types should produce different IDs."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        id1 = EntityIdGenerator.generate("person", "alice")
        id2 = EntityIdGenerator.generate("repository", "alice")
        assert id1 != id2

    def test_hash_portion_is_hex(self):
        """Hash portion of ID should be valid hex."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        id_value = EntityIdGenerator.generate("person", "alice")
        hash_part = id_value.split(":")[1]
        # Should be valid hex characters
        assert all(c in "0123456789abcdef" for c in hash_part)

    def test_hash_portion_length(self):
        """Hash should be 16 characters (truncated SHA256)."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        id_value = EntityIdGenerator.generate("person", "alice")
        hash_part = id_value.split(":")[1]
        assert len(hash_part) == 16

    def test_normalizes_entity_type_to_lowercase(self):
        """Entity type should be normalized to lowercase in both prefix and hash."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        id1 = EntityIdGenerator.generate("Person", "alice-smith")
        id2 = EntityIdGenerator.generate("person", "alice-smith")
        id3 = EntityIdGenerator.generate("PERSON", "alice-smith")

        # All should be identical
        assert id1 == id2 == id3
        # All should have lowercase prefix
        assert id1.startswith("person:")
        assert id2.startswith("person:")
        assert id3.startswith("person:")

    def test_tenant_id_affects_hash(self):
        """Different tenant_ids should produce different IDs (when implemented)."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        # With default tenant_id (currently "")
        id1 = EntityIdGenerator.generate("person", "alice")
        id2 = EntityIdGenerator.generate("person", "alice", tenant_id="")

        assert id1 == id2

        # When tenant_id is properly implemented, different tenants should get different IDs
        # This test documents the intended behavior for future implementation
        id_tenant_a = EntityIdGenerator.generate(
            "person", "alice", tenant_id="tenant-a"
        )
        id_tenant_b = EntityIdGenerator.generate(
            "person", "alice", tenant_id="tenant-b"
        )

        # These should differ once tenant_id is properly incorporated
        assert id_tenant_a != id_tenant_b

    def test_special_characters_in_slug(self):
        """Should handle special characters in slug."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        id_value = EntityIdGenerator.generate("person", "alice-smith@example.com")
        assert id_value.startswith("person:")
        assert len(id_value.split(":")[1]) == 16

    def test_unicode_slug(self):
        """Should handle unicode characters in slug."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        id_value = EntityIdGenerator.generate("person", "alice-müller")
        assert id_value.startswith("person:")
        assert len(id_value.split(":")[1]) == 16

    def test_consistency_across_calls(self):
        """Multiple calls with same inputs should always produce same output."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        ids = [
            EntityIdGenerator.generate("repository", "kartograph") for _ in range(100)
        ]

        # All IDs should be identical
        assert len(set(ids)) == 1


class TestEntityIdGeneratorValidation:
    """Test suite for EntityIdGenerator input validation."""

    def test_rejects_none_entity_type(self):
        """Should raise ValueError for None entity_type."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        with pytest.raises(ValueError, match="entity_type must be a non-None string"):
            EntityIdGenerator.generate(None, "alice")

    def test_rejects_none_entity_slug(self):
        """Should raise ValueError for None entity_slug."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        with pytest.raises(ValueError, match="entity_slug must be a non-None string"):
            EntityIdGenerator.generate("person", None)

    def test_rejects_empty_entity_type(self):
        """Should raise ValueError for empty entity_type."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        with pytest.raises(
            ValueError, match="entity_type must not be empty or whitespace-only"
        ):
            EntityIdGenerator.generate("", "alice")

    def test_rejects_empty_entity_slug(self):
        """Should raise ValueError for empty entity_slug."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        with pytest.raises(
            ValueError, match="entity_slug must not be empty or whitespace-only"
        ):
            EntityIdGenerator.generate("person", "")

    def test_rejects_whitespace_only_entity_type(self):
        """Should raise ValueError for whitespace-only entity_type."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        with pytest.raises(
            ValueError, match="entity_type must not be empty or whitespace-only"
        ):
            EntityIdGenerator.generate("   ", "alice")

    def test_rejects_whitespace_only_entity_slug(self):
        """Should raise ValueError for whitespace-only entity_slug."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        with pytest.raises(
            ValueError, match="entity_slug must not be empty or whitespace-only"
        ):
            EntityIdGenerator.generate("person", "   ")

    def test_strips_whitespace_from_entity_type(self):
        """Should strip leading/trailing whitespace from entity_type."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        id1 = EntityIdGenerator.generate("  person  ", "alice")
        id2 = EntityIdGenerator.generate("person", "alice")

        # Should be identical after stripping
        assert id1 == id2
        assert id1.startswith("person:")

    def test_strips_whitespace_from_entity_slug(self):
        """Should strip leading/trailing whitespace from entity_slug."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        id1 = EntityIdGenerator.generate("person", "  alice  ")
        id2 = EntityIdGenerator.generate("person", "alice")

        # Should be identical after stripping
        assert id1 == id2

    def test_handles_none_tenant_id(self):
        """Should treat None tenant_id as empty string."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        id1 = EntityIdGenerator.generate("person", "alice", tenant_id=None)
        id2 = EntityIdGenerator.generate("person", "alice", tenant_id="")

        # Should be identical
        assert id1 == id2

    def test_rejects_non_string_entity_type(self):
        """Should reject non-string entity_type."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        with pytest.raises(ValueError, match="entity_type must be a non-None string"):
            EntityIdGenerator.generate(123, "alice")

    def test_rejects_non_string_entity_slug(self):
        """Should reject non-string entity_slug."""
        from shared_kernel.graph_primitives import EntityIdGenerator

        with pytest.raises(ValueError, match="entity_slug must be a non-None string"):
            EntityIdGenerator.generate("person", 123)
