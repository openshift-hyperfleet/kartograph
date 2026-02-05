"""Tests for system properties documentation export.

This test ensures that the documentation stays in sync with the actual code
by validating the exported system-properties.json file matches the source.

This follows the "living documentation" pattern where docs are tested just
like code to prevent documentation drift.
"""

import json
from pathlib import Path

import pytest

from graph.domain.value_objects import (
    COMMON_SYSTEM_PROPERTIES,
    EDGE_SYSTEM_PROPERTIES,
    NODE_SYSTEM_PROPERTIES,
    EntityType,
    get_system_properties_for_entity,
)


class TestSystemPropertiesExport:
    """Validate exported system properties match source code."""

    @pytest.fixture
    def exported_json_path(self):
        """Path to the exported JSON file used by documentation."""
        return (
            Path(__file__).parent.parent.parent.parent.parent.parent
            / "website"
            / "src"
            / "data"
            / "system-properties.json"
        )

    def test_exported_json_exists(self, exported_json_path):
        """The exported JSON file must exist for docs to work."""
        assert exported_json_path.exists(), (
            f"System properties JSON not found at {exported_json_path}. "
            "Run 'cd src/api && uv run python ../../scripts/export_system_properties.py' to generate it."
        )

    def test_exported_common_properties_match_code(self, exported_json_path):
        """Common system properties in JSON must match source code."""
        with open(exported_json_path) as f:
            data = json.load(f)

        exported_common = set(data["common"]["properties"])
        actual_common = COMMON_SYSTEM_PROPERTIES

        assert exported_common == actual_common, (
            f"Exported common properties {exported_common} don't match "
            f"actual {actual_common}. Re-run export script to sync."
        )

    def test_exported_node_properties_match_code(self, exported_json_path):
        """Node system properties in JSON must match source code."""
        with open(exported_json_path) as f:
            data = json.load(f)

        exported_node_total = set(data["node_total"]["properties"])
        actual_node_total = get_system_properties_for_entity(EntityType.NODE)

        assert exported_node_total == actual_node_total, (
            f"Exported node properties {exported_node_total} don't match "
            f"actual {actual_node_total}. Re-run export script to sync."
        )

    def test_exported_edge_properties_match_code(self, exported_json_path):
        """Edge system properties in JSON must match source code."""
        with open(exported_json_path) as f:
            data = json.load(f)

        exported_edge_total = set(data["edge_total"]["properties"])
        actual_edge_total = get_system_properties_for_entity(EntityType.EDGE)

        assert exported_edge_total == actual_edge_total, (
            f"Exported edge properties {exported_edge_total} don't match "
            f"actual {actual_edge_total}. Re-run export script to sync."
        )

    def test_exported_node_specific_properties_match_code(self, exported_json_path):
        """Node-specific system properties in JSON must match source code."""
        with open(exported_json_path) as f:
            data = json.load(f)

        exported_node_specific = set(data["node_specific"]["properties"])
        actual_node_specific = NODE_SYSTEM_PROPERTIES

        assert exported_node_specific == actual_node_specific, (
            f"Exported node-specific properties {exported_node_specific} don't match "
            f"actual {actual_node_specific}. Re-run export script to sync."
        )

    def test_exported_edge_specific_properties_match_code(self, exported_json_path):
        """Edge-specific system properties in JSON must match source code."""
        with open(exported_json_path) as f:
            data = json.load(f)

        exported_edge_specific = set(data["edge_specific"]["properties"])
        actual_edge_specific = EDGE_SYSTEM_PROPERTIES

        assert exported_edge_specific == actual_edge_specific, (
            f"Exported edge-specific properties {exported_edge_specific} don't match "
            f"actual {actual_edge_specific}. Re-run export script to sync."
        )

    def test_metadata_present(self, exported_json_path):
        """Exported JSON should include generation metadata."""
        with open(exported_json_path) as f:
            data = json.load(f)

        assert "_metadata" in data, "Metadata section missing from exported JSON"
        assert "generated_by" in data["_metadata"]
        assert "source" in data["_metadata"]
        assert data["_metadata"]["source"] == "src/api/graph/domain/value_objects.py"
