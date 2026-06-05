"""System prompt assembly for the Graph Management Assistant."""

from __future__ import annotations

from typing import Any, Literal

PromptDetail = Literal["full", "compact"]

from kartograph_agent_runtime.schema_tools import (
    KARTOGRAPH_SCHEMA_TOOL_NAMES,
    WORKSPACE_FILE_TOOL_NAMES,
)
from kartograph_agent_runtime.settings import AgentRuntimeSettings

_TOOLS_QUICK_REFERENCE = """
## Kartograph schema tools (always use these — never probe HTTP routes)

| Tool | Purpose |
|------|---------|
| `kartograph_get_schema_authoring_guide` | Full JSON shapes, instance cookbook, mutation rules — call first |
| `kartograph_get_workspace_readiness` | Prepopulated gaps, live instance counts, blocking reasons |
| `kartograph_get_schema_ontology` | Read current `node_types` and `edge_types` before every save |
| `kartograph_save_schema_ontology` | Replace canonical ontology (read → merge edits → save full payload) |
| `kartograph_validate_graph_mutations` | Dry-run JSONL (strict CREATE — no duplicates) |
| `kartograph_apply_graph_mutations` | Apply JSONL CREATE/UPDATE/DELETE (small batches) |
| `kartograph_validate_graph_mutations_from_file` | Dry-run a workspace `.jsonl` file |
| `kartograph_apply_graph_mutations_from_file` | Apply a workspace `.jsonl` file in one call |
| `kartograph_list_instances_by_type` | List/count entity instances for one type (verify prepopulation) |
| `kartograph_list_relationship_instances` | List relationship edges with source/target slugs and node IDs |
| `kartograph_search_graph_by_slug` | Find existing nodes by slug to avoid duplicates |
| `kartograph_check_graph_slugs` | Batch check which slugs already exist for one entity type |

## Workspace tools

| Tool | Purpose |
|------|---------|
| `Read` | Read files under the session workspace mount |
| `Grep` | Search file contents in `repository-files/<data_source>/` |
| `Glob` | List files by pattern for instance generation |
| `Bash` | Run `instance_generators/*.py` against `repository-files/` (workspace only) |

### Quick workflow

1. `kartograph_get_schema_authoring_guide`
2. `kartograph_get_workspace_readiness`
3. `kartograph_get_schema_ontology`
4. Prepopulation: `{label}.py` → `out/{label}_instances.json` → `entities_to_jsonl.py` → apply-from-file
5. Model types → `kartograph_save_schema_ontology`
6. Apply CREATE mutations → `kartograph_apply_graph_mutations` (small fixes inline; bulk via generator output)
7. Create relationship edges after entity IDs are known
8. Verify with `kartograph_list_instances_by_type` and `kartograph_get_workspace_readiness`

Writes persist to the platform database for the active knowledge graph.
""".strip()

_TOOLS_COMPACT_REFERENCE = (
    "Tools: kartograph_* schema MCP tools, plus Read/Grep/Glob/Bash. "
    "Prepopulation: {label}.py → out/{label}_instances.json → entities_to_jsonl.py or "
    "relationships_to_jsonl.py → validate/apply out/{label}_instances.jsonl. Never /tmp."
)


def _format_workspace_readiness(readiness: dict[str, Any]) -> str:
    lines = ["## Workspace readiness (live snapshot)"]

    entity_gaps = readiness.get("prepopulated_entity_types_without_instances_live") or []
    rel_gaps = readiness.get("prepopulated_relationship_types_without_instances_live") or []
    blocking = readiness.get("blocking_reasons") or []
    prepopulated_types = readiness.get("prepopulated_entity_types") or []
    prepopulated_relationships = readiness.get("prepopulated_relationship_types") or []

    if entity_gaps:
        lines.append(
            "- Prepopulated entity types still needing instances: "
            + ", ".join(f"`{label}`" for label in entity_gaps)
        )
    else:
        lines.append("- All prepopulated entity types have at least one live instance.")

    if rel_gaps:
        lines.append(
            "- Prepopulated relationship types still needing instances: "
            + ", ".join(f"`{key}`" for key in rel_gaps)
        )

    if prepopulated_types:
        lines.append("- Prepopulated entity coverage:")
        for row in prepopulated_types:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or "?")
            live = row.get("live_instance_count", 0)
            metadata = row.get("metadata_instance_count", 0)
            lines.append(f"  - `{label}`: live={live}, metadata={metadata}")

    if prepopulated_relationships:
        lines.append("- Prepopulated relationship coverage:")
        for row in prepopulated_relationships:
            if not isinstance(row, dict):
                continue
            key = str(row.get("key") or "?")
            live = row.get("live_instance_count", 0)
            metadata = row.get("metadata_instance_count", 0)
            lines.append(f"  - `{key}`: live={live}, metadata={metadata}")

    if blocking:
        lines.append("- Blocking reasons:")
        for reason in blocking:
            lines.append(f"  - {reason}")

    transition = readiness.get("transition_eligible")
    live_ready = readiness.get("prepopulated_types_ready_live")
    if transition is not None:
        lines.append(f"- Transition eligible: `{transition}`")
    if live_ready is not None:
        lines.append(f"- Prepopulated coverage ready (live): `{live_ready}`")

    return "\n".join(lines)


def build_agent_system_prompt(
    agent_configuration: dict[str, Any],
    *,
    settings: AgentRuntimeSettings | None = None,
    workspace_appendix: str = "",
    workspace_readiness: dict[str, Any] | None = None,
    include_tools_manifest: bool = True,
    prompt_detail: PromptDetail = "full",
) -> str:
    """Build the system prompt with guardrails, optional skills/tools, and session scope."""
    system_prompt = str(agent_configuration.get("system_prompt") or "").strip()
    guardrails = agent_configuration.get("guardrails") or []
    skills = agent_configuration.get("skills") or {}
    prompt_hierarchy = agent_configuration.get("prompt_hierarchy") or []
    ui_mode = str(agent_configuration.get("graph_management_ui_mode") or "").strip()

    guardrail_lines = "\n".join(f"- {item}" for item in guardrails if str(item).strip())

    skill_sections: list[str] = []
    if prompt_hierarchy:
        hierarchy_line = " → ".join(str(item) for item in prompt_hierarchy if str(item).strip())
        if hierarchy_line:
            skill_sections.append(f"Prompt hierarchy: {hierarchy_line}")
    if ui_mode:
        skill_sections.append(f"UI mode: {ui_mode}")

    for key, value in sorted(skills.items()):
        text = str(value).strip()
        if text:
            skill_sections.append(f"**{key}**: {text}")

    skills_block = ""
    if prompt_detail == "full" and skill_sections:
        skills_block = "## Skills\n\n" + "\n\n".join(skill_sections)

    tools_block = ""
    if include_tools_manifest and settings is not None and settings.workload_token.strip():
        if prompt_detail == "compact":
            tools_block = f"## Tools\n\n{_TOOLS_COMPACT_REFERENCE}"
        else:
            kartograph_tools = ", ".join(f"`{name}`" for name in KARTOGRAPH_SCHEMA_TOOL_NAMES)
            file_tools = ", ".join(f"`{name}`" for name in WORKSPACE_FILE_TOOL_NAMES)
            tools_block = (
                f"{_TOOLS_QUICK_REFERENCE}\n\n"
                f"Registered Kartograph tools: {kartograph_tools}.\n"
                f"Registered workspace tools: {file_tools}."
            )

    session_block = ""
    if settings is not None:
        kg_id = settings.knowledge_graph_id.strip()
        tenant_id = settings.tenant_id.strip()
        if kg_id or tenant_id:
            lines = ["## Session scope"]
            if kg_id:
                lines.append(f"- Knowledge graph: `{kg_id}`")
            if tenant_id:
                lines.append(f"- Tenant: `{tenant_id}`")
            lines.append(
                "- All Kartograph schema tool writes target this knowledge graph automatically."
            )
            session_block = "\n".join(lines)

    readiness_block = ""
    if workspace_readiness:
        readiness_block = _format_workspace_readiness(workspace_readiness)

    sections = [
        section
        for section in (
            system_prompt,
            guardrail_lines,
            skills_block,
            tools_block,
            readiness_block,
            session_block,
            workspace_appendix.strip(),
        )
        if section
    ]
    return "\n\n".join(sections) or "You are the Graph Management Assistant."
