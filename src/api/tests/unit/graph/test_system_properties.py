"""Unit tests for system properties helpers."""

import pytest

from graph.domain.value_objects import (
    COMMON_SYSTEM_PROPERTIES,
    EDGE_SYSTEM_PROPERTIES,
    EntityType,
    NODE_SYSTEM_PROPERTIES,
    get_system_properties_for_entity,
)


class TestSystemPropertiesConstants:
    """Tests for system property constants."""

    def test_common_system_properties_defined(self):
        """Should define common system properties."""
        assert "data_source_id" in COMMON_SYSTEM_PROPERTIES
        assert "source_path" in COMMON_SYSTEM_PROPERTIES

    def test_node_system_properties_defined(self):
        """Should define node-specific system properties."""
        assert "slug" in NODE_SYSTEM_PROPERTIES

    def test_edge_system_properties_defined(self):
        """Should define edge-specific system properties (extensible)."""
        # Currently empty, but defined for future use
        assert isinstance(EDGE_SYSTEM_PROPERTIES, frozenset)


class TestGetSystemPropertiesForEntity:
    """Tests for get_system_properties_for_entity helper."""

    def test_returns_node_system_properties(self):
        """Should return common + node-specific properties for nodes."""
        props = get_system_properties_for_entity(EntityType.NODE)

        # Should include common properties
        assert "data_source_id" in props
        assert "source_path" in props

        # Should include node-specific properties
        assert "slug" in props

    def test_returns_edge_system_properties(self):
        """Should return common + edge-specific properties for edges."""
        props = get_system_properties_for_entity(EntityType.EDGE)

        # Should include common properties
        assert "data_source_id" in props
        assert "source_path" in props

        # Should NOT include node-specific properties
        assert "slug" not in props

    def test_raises_on_invalid_entity_type(self):
        """Should raise ValueError for invalid entity type."""
        with pytest.raises(ValueError) as exc_info:
            # This shouldn't be possible with enum, but test defensive code
            get_system_properties_for_entity("invalid")  # type: ignore

        assert "invalid" in str(exc_info.value).lower()
