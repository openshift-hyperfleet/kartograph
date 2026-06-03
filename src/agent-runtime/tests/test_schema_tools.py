"""Unit tests for Kartograph schema MCP tools."""

from __future__ import annotations

from kartograph_agent_runtime.schema_tools import (
    KARTOGRAPH_SCHEMA_TOOL_NAMES,
    build_kartograph_schema_mcp_server,
)
from kartograph_agent_runtime.settings import AgentRuntimeSettings
from kartograph_agent_runtime.tools import RuntimeTooling


def test_schema_tool_names_cover_authoring_surface() -> None:
    assert "kartograph_get_schema_authoring_guide" in KARTOGRAPH_SCHEMA_TOOL_NAMES
    assert "kartograph_get_schema_ontology" in KARTOGRAPH_SCHEMA_TOOL_NAMES
    assert "kartograph_save_schema_ontology" in KARTOGRAPH_SCHEMA_TOOL_NAMES
    assert "kartograph_apply_graph_mutations" in KARTOGRAPH_SCHEMA_TOOL_NAMES


def test_build_kartograph_schema_mcp_server_registers_tools() -> None:
    tooling = RuntimeTooling(
        settings=AgentRuntimeSettings(
            KARTOGRAPH_WORKLOAD_TOKEN="token",
            KARTOGRAPH_API_BASE_URL="http://api:8000",
        )
    )
    server = build_kartograph_schema_mcp_server(tooling)
    assert server["type"] == "sdk"
    assert server["name"] == "kartograph"
