"""In-process MCP tools for Kartograph schema authoring."""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from kartograph_agent_runtime.tools import RuntimeTooling

KARTOGRAPH_SCHEMA_TOOL_NAMES = (
    "kartograph_get_schema_authoring_guide",
    "kartograph_get_schema_ontology",
    "kartograph_save_schema_ontology",
    "kartograph_apply_graph_mutations",
    "kartograph_search_graph_by_slug",
)


def build_kartograph_schema_mcp_server(tooling: RuntimeTooling):
    """Register Kartograph schema tools on an SDK MCP server."""

    @tool(
        "kartograph_get_schema_authoring_guide",
        "Return instructions for authoring entity types, relationship types, and instances in Kartograph.",
        {},
    )
    async def get_schema_authoring_guide(_args: dict[str, Any]) -> dict[str, Any]:
        try:
            payload = await tooling.get_schema_authoring_guide()
            guide = str(payload.get("guide") or "")
            return {"content": [{"type": "text", "text": guide}]}
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [{"type": "text", "text": f"Failed to load schema guide: {exc}"}],
                "is_error": True,
            }

    @tool(
        "kartograph_get_schema_ontology",
        "Read the current canonical ontology (node_types and edge_types) for this knowledge graph.",
        {},
    )
    async def get_schema_ontology(_args: dict[str, Any]) -> dict[str, Any]:
        try:
            return RuntimeTooling.format_tool_result(await tooling.get_schema_ontology())
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [{"type": "text", "text": f"Failed to read ontology: {exc}"}],
                "is_error": True,
            }

    @tool(
        "kartograph_save_schema_ontology",
        "Replace the canonical ontology. Pass full node_types and edge_types arrays.",
        {
            "node_types": list,
            "edge_types": list,
            "approved_at": str,
        },
    )
    async def save_schema_ontology(args: dict[str, Any]) -> dict[str, Any]:
        ontology = {
            "node_types": args.get("node_types") or [],
            "edge_types": args.get("edge_types") or [],
        }
        approved_at = args.get("approved_at")
        if isinstance(approved_at, str) and approved_at.strip():
            ontology["approved_at"] = approved_at.strip()
        try:
            return RuntimeTooling.format_tool_result(
                await tooling.save_schema_ontology(ontology=ontology),
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [{"type": "text", "text": f"Failed to save ontology: {exc}"}],
                "is_error": True,
            }

    @tool(
        "kartograph_apply_graph_mutations",
        "Apply JSONL mutation lines to create/update/delete entity or relationship instances.",
        {"jsonl": str},
    )
    async def apply_graph_mutations(args: dict[str, Any]) -> dict[str, Any]:
        jsonl = str(args.get("jsonl") or "").strip()
        if not jsonl:
            return {
                "content": [{"type": "text", "text": "jsonl must not be empty."}],
                "is_error": True,
            }
        try:
            return RuntimeTooling.format_tool_result(
                await tooling.apply_graph_mutations(jsonl=jsonl),
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [{"type": "text", "text": f"Failed to apply mutations: {exc}"}],
                "is_error": True,
            }

    @tool(
        "kartograph_search_graph_by_slug",
        "Search existing graph nodes by slug within the active knowledge graph.",
        {"slug": str, "entity_type": str},
    )
    async def search_graph_by_slug(args: dict[str, Any]) -> dict[str, Any]:
        slug = str(args.get("slug") or "").strip()
        if not slug:
            return {
                "content": [{"type": "text", "text": "slug must not be empty."}],
                "is_error": True,
            }
        entity_type = args.get("entity_type")
        try:
            return RuntimeTooling.format_tool_result(
                await tooling.search_graph_by_slug(
                    slug=slug,
                    entity_type=str(entity_type).strip() if entity_type else None,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [{"type": "text", "text": f"Graph search failed: {exc}"}],
                "is_error": True,
            }

    return create_sdk_mcp_server(
        name="kartograph",
        version="1.0.0",
        tools=[
            get_schema_authoring_guide,
            get_schema_ontology,
            save_schema_ontology,
            apply_graph_mutations,
            search_graph_by_slug,
        ],
    )
