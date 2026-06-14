"""In-process MCP tools for Kartograph schema authoring."""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from kartograph_agent_runtime.extraction_jobs_tools import (
    KARTOGRAPH_EXTRACTION_JOBS_TOOL_NAMES,
    append_extraction_jobs_tools,
)
from kartograph_agent_runtime.tools import RuntimeTooling

WORKSPACE_FILE_TOOL_NAMES = ("Read", "Write", "Edit", "Grep", "Glob", "Bash")

KARTOGRAPH_SCHEMA_TOOL_NAMES = (
    "kartograph_get_schema_authoring_guide",
    "kartograph_get_workspace_readiness",
    "kartograph_get_schema_ontology",
    "kartograph_save_schema_ontology",
    "kartograph_validate_graph_mutations",
    "kartograph_apply_graph_mutations",
    "kartograph_validate_graph_mutations_from_file",
    "kartograph_apply_graph_mutations_from_file",
    "kartograph_list_instances_by_type",
    "kartograph_list_relationship_instances",
    "kartograph_search_graph_by_slug",
    "kartograph_check_graph_slugs",
)

GMA_ALLOWED_TOOL_NAMES = (
    KARTOGRAPH_SCHEMA_TOOL_NAMES + KARTOGRAPH_EXTRACTION_JOBS_TOOL_NAMES + WORKSPACE_FILE_TOOL_NAMES
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
        "kartograph_get_workspace_readiness",
        "Return bootstrap readiness: prepopulated gaps, live instance counts, and blocking reasons.",
        {},
    )
    async def get_workspace_readiness(_args: dict[str, Any]) -> dict[str, Any]:
        try:
            return RuntimeTooling.format_tool_result(await tooling.get_workspace_readiness())
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [{"type": "text", "text": f"Failed to load workspace readiness: {exc}"}],
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
        "kartograph_validate_graph_mutations",
        "Dry-run: validate JSONL mutations without writing (CREATE/UPDATE/DELETE).",
        {"jsonl": str},
    )
    async def validate_graph_mutations(args: dict[str, Any]) -> dict[str, Any]:
        jsonl = str(args.get("jsonl") or "").strip()
        if not jsonl:
            return {
                "content": [{"type": "text", "text": "jsonl must not be empty."}],
                "is_error": True,
            }
        try:
            return RuntimeTooling.format_tool_result(
                await tooling.validate_graph_mutations(jsonl=jsonl),
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [{"type": "text", "text": f"Failed to validate mutations: {exc}"}],
                "is_error": True,
            }

    @tool(
        "kartograph_apply_graph_mutations",
        "Apply JSONL mutation lines (CREATE, UPDATE, DELETE). CREATE fails on duplicates; UPDATE/DELETE require existing ids.",
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
        "kartograph_validate_graph_mutations_from_file",
        "Dry-run validate a .jsonl file under the workspace (path relative to session root).",
        {"path": str},
    )
    async def validate_graph_mutations_from_file(args: dict[str, Any]) -> dict[str, Any]:
        path = str(args.get("path") or "").strip()
        if not path:
            return {
                "content": [{"type": "text", "text": "path must not be empty."}],
                "is_error": True,
            }
        try:
            return RuntimeTooling.format_tool_result(
                await tooling.validate_graph_mutations_from_file(path=path),
            )
        except ValueError as exc:
            return {
                "content": [{"type": "text", "text": str(exc)}],
                "is_error": True,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [{"type": "text", "text": f"Failed to validate file: {exc}"}],
                "is_error": True,
            }

    @tool(
        "kartograph_apply_graph_mutations_from_file",
        "Apply a workspace .jsonl file in one call (CREATE/UPDATE/DELETE). Apply pre-validates.",
        {"path": str},
    )
    async def apply_graph_mutations_from_file(args: dict[str, Any]) -> dict[str, Any]:
        path = str(args.get("path") or "").strip()
        if not path:
            return {
                "content": [{"type": "text", "text": "path must not be empty."}],
                "is_error": True,
            }
        try:
            return RuntimeTooling.format_tool_result(
                await tooling.apply_graph_mutations_from_file(path=path),
            )
        except ValueError as exc:
            return {
                "content": [{"type": "text", "text": str(exc)}],
                "is_error": True,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [{"type": "text", "text": f"Failed to apply file: {exc}"}],
                "is_error": True,
            }

    @tool(
        "kartograph_list_instances_by_type",
        "List entity instances for one type with pagination (use to verify prepopulation).",
        {"entity_type": str, "limit": int, "offset": int},
    )
    async def list_instances_by_type(args: dict[str, Any]) -> dict[str, Any]:
        entity_type = str(args.get("entity_type") or "").strip()
        if not entity_type:
            return {
                "content": [{"type": "text", "text": "entity_type must not be empty."}],
                "is_error": True,
            }
        limit = args.get("limit", 100)
        offset = args.get("offset", 0)
        try:
            return RuntimeTooling.format_tool_result(
                await tooling.list_instances_by_type(
                    entity_type=entity_type,
                    limit=int(limit) if isinstance(limit, int) else 100,
                    offset=int(offset) if isinstance(offset, int) else 0,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [{"type": "text", "text": f"Failed to list instances: {exc}"}],
                "is_error": True,
            }

    @tool(
        "kartograph_list_relationship_instances",
        "List relationship instances with source/target slugs and IDs for edge prepopulation.",
        {
            "relationship_type": str,
            "source_entity_type": str,
            "target_entity_type": str,
            "limit": int,
            "offset": int,
        },
    )
    async def list_relationship_instances(args: dict[str, Any]) -> dict[str, Any]:
        relationship_type = str(args.get("relationship_type") or "").strip()
        if not relationship_type:
            return {
                "content": [{"type": "text", "text": "relationship_type must not be empty."}],
                "is_error": True,
            }
        source_entity_type = args.get("source_entity_type")
        target_entity_type = args.get("target_entity_type")
        limit = args.get("limit", 100)
        offset = args.get("offset", 0)
        try:
            return RuntimeTooling.format_tool_result(
                await tooling.list_relationship_instances(
                    relationship_type=relationship_type,
                    source_entity_type=str(source_entity_type).strip()
                    if source_entity_type
                    else None,
                    target_entity_type=str(target_entity_type).strip()
                    if target_entity_type
                    else None,
                    limit=int(limit) if isinstance(limit, int) else 100,
                    offset=int(offset) if isinstance(offset, int) else 0,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [{"type": "text", "text": f"Failed to list relationships: {exc}"}],
                "is_error": True,
            }

    @tool(
        "kartograph_check_graph_slugs",
        "Check which slugs already exist for one entity type (before bulk CREATE).",
        {"entity_type": str, "slugs": list},
    )
    async def check_graph_slugs(args: dict[str, Any]) -> dict[str, Any]:
        entity_type = str(args.get("entity_type") or "").strip()
        slugs = args.get("slugs") or []
        if not entity_type:
            return {
                "content": [{"type": "text", "text": "entity_type must not be empty."}],
                "is_error": True,
            }
        if not isinstance(slugs, list) or not slugs:
            return {
                "content": [{"type": "text", "text": "slugs must be a non-empty list."}],
                "is_error": True,
            }
        try:
            return RuntimeTooling.format_tool_result(
                await tooling.check_graph_slugs(
                    entity_type=entity_type,
                    slugs=[str(slug).strip() for slug in slugs if str(slug).strip()],
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [{"type": "text", "text": f"Slug check failed: {exc}"}],
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

    mcp_tools: list[Any] = [
        get_schema_authoring_guide,
        get_workspace_readiness,
        get_schema_ontology,
        save_schema_ontology,
        validate_graph_mutations,
        apply_graph_mutations,
        validate_graph_mutations_from_file,
        apply_graph_mutations_from_file,
        list_instances_by_type,
        list_relationship_instances,
        search_graph_by_slug,
        check_graph_slugs,
    ]
    append_extraction_jobs_tools(tooling=tooling, tools=mcp_tools)

    return create_sdk_mcp_server(
        name="kartograph",
        version="1.0.0",
        tools=mcp_tools,
    )
