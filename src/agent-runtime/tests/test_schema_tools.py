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
    assert "kartograph_get_workspace_readiness" in KARTOGRAPH_SCHEMA_TOOL_NAMES
    assert "kartograph_get_schema_ontology" in KARTOGRAPH_SCHEMA_TOOL_NAMES
    assert "kartograph_save_schema_ontology" in KARTOGRAPH_SCHEMA_TOOL_NAMES
    assert "kartograph_validate_graph_mutations" in KARTOGRAPH_SCHEMA_TOOL_NAMES
    assert "kartograph_apply_graph_mutations" in KARTOGRAPH_SCHEMA_TOOL_NAMES
    assert "kartograph_apply_graph_mutations_from_file" in KARTOGRAPH_SCHEMA_TOOL_NAMES
    assert "kartograph_check_graph_slugs" in KARTOGRAPH_SCHEMA_TOOL_NAMES
    assert "kartograph_list_instances_by_type" in KARTOGRAPH_SCHEMA_TOOL_NAMES
    assert "kartograph_list_relationship_instances" in KARTOGRAPH_SCHEMA_TOOL_NAMES


def test_gma_allowed_tools_include_workspace_file_tools() -> None:
    from kartograph_agent_runtime.schema_tools import GMA_ALLOWED_TOOL_NAMES, WORKSPACE_FILE_TOOL_NAMES

    for tool_name in WORKSPACE_FILE_TOOL_NAMES:
        assert tool_name in GMA_ALLOWED_TOOL_NAMES


def test_gma_allowed_tools_include_write_and_edit() -> None:
    from kartograph_agent_runtime.schema_tools import GMA_ALLOWED_TOOL_NAMES

    assert "Write" in GMA_ALLOWED_TOOL_NAMES
    assert "Edit" in GMA_ALLOWED_TOOL_NAMES


def test_gma_allowed_tools_include_bash() -> None:
    from kartograph_agent_runtime.schema_tools import GMA_ALLOWED_TOOL_NAMES

    assert "Bash" in GMA_ALLOWED_TOOL_NAMES


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
