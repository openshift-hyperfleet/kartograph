#!/usr/bin/env python3
"""Export system properties from code to JSON for documentation.

This script extracts system property definitions from the source code and
exports them as JSON, enabling the documentation to stay in sync automatically.
This follows the "living documentation" pattern where docs are generated from
the actual source of truth (the code).

Run this during the build process or CI pipeline to keep docs up-to-date.
"""

import json
import sys
from pathlib import Path

# Add src/api to path so we can import from it
src_api_path = Path(__file__).parent.parent / "src" / "api"
sys.path.insert(0, str(src_api_path))

from graph.domain.value_objects import (  # noqa: E402
    COMMON_SYSTEM_PROPERTIES,
    EDGE_SYSTEM_PROPERTIES,
    NODE_SYSTEM_PROPERTIES,
    EntityType,
    get_system_properties_for_entity,
)


def export_system_properties():
    """Export system properties to JSON for documentation consumption."""
    # Property descriptions for documentation
    property_descriptions = {
        "data_source_id": "Identifies which data source this entity came from (e.g., 'ds-123')",
        "source_path": "The file path within the data source where this entity was extracted from",
        "slug": "Unique human-readable identifier for the node (e.g., 'alice-smith', 'kartograph')",
    }

    data = {
        "common": {
            "description": "System properties required for all entities (nodes and edges)",
            "properties": sorted(list(COMMON_SYSTEM_PROPERTIES)),
            "property_descriptions": {
                prop: property_descriptions.get(prop, "")
                for prop in COMMON_SYSTEM_PROPERTIES
            },
        },
        "node_specific": {
            "description": "Additional system properties required only for nodes",
            "properties": sorted(list(NODE_SYSTEM_PROPERTIES)),
            "property_descriptions": {
                prop: property_descriptions.get(prop, "")
                for prop in NODE_SYSTEM_PROPERTIES
            },
        },
        "edge_specific": {
            "description": "Additional system properties required only for edges",
            "properties": sorted(list(EDGE_SYSTEM_PROPERTIES)),
            "property_descriptions": {
                prop: property_descriptions.get(prop, "")
                for prop in EDGE_SYSTEM_PROPERTIES
            },
        },
        "node_total": {
            "description": "All system properties for nodes (common + node-specific)",
            "properties": sorted(
                list(get_system_properties_for_entity(EntityType.NODE))
            ),
        },
        "edge_total": {
            "description": "All system properties for edges (common + edge-specific)",
            "properties": sorted(
                list(get_system_properties_for_entity(EntityType.EDGE))
            ),
        },
        "_metadata": {
            "generated_by": "scripts/export-system-properties.py",
            "source": "src/api/graph/domain/value_objects.py",
            "description": "Auto-generated system property definitions. DO NOT EDIT manually. Run 'python scripts/export-system-properties.py' to regenerate.",
        },
    }

    # Write to website data directory
    output_path = (
        Path(__file__).parent.parent
        / "website"
        / "src"
        / "data"
        / "system-properties.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")  # Add trailing newline for POSIX compliance

    print(f"✅ Exported system properties to {output_path}")
    print(f"   - Common: {data['common']['properties']}")
    print(f"   - Node total: {data['node_total']['properties']}")
    print(f"   - Edge total: {data['edge_total']['properties']}")

    return output_path


if __name__ == "__main__":
    export_system_properties()
