"""System prompt assembly for the Graph Management Assistant."""

from __future__ import annotations

from typing import Any

from kartograph_agent_runtime.schema_tools import KARTOGRAPH_SCHEMA_TOOL_NAMES
from kartograph_agent_runtime.settings import AgentRuntimeSettings

_TOOLS_QUICK_REFERENCE = """
## Kartograph schema tools (always use these — never probe HTTP routes)

| Tool | Purpose |
|------|---------|
| `kartograph_get_schema_authoring_guide` | Full JSON shapes and mutation rules — call first on schema tasks |
| `kartograph_get_schema_ontology` | Read current `node_types` and `edge_types` before every save |
| `kartograph_save_schema_ontology` | Replace canonical ontology (read → merge edits → save full payload) |
| `kartograph_apply_graph_mutations` | Apply JSONL CREATE/UPDATE/DELETE instance lines to the official graph DB |
| `kartograph_search_graph_by_slug` | Find existing nodes by slug to avoid duplicates |

### Quick workflow

1. `kartograph_get_schema_authoring_guide`
2. `kartograph_get_schema_ontology`
3. Model entity/relationship types → `kartograph_save_schema_ontology`
4. Create instances → `kartograph_apply_graph_mutations` (one JSON object per line)
5. Verify → `kartograph_search_graph_by_slug`

Writes persist to the platform database for the active knowledge graph. Use Read/Grep/Glob
only for repository files under the session workspace — not for API discovery.
""".strip()


def build_agent_system_prompt(
    agent_configuration: dict[str, Any],
    *,
    settings: AgentRuntimeSettings | None = None,
    workspace_appendix: str = "",
    include_tools_manifest: bool = True,
) -> str:
    """Build the full system prompt with skills, guardrails, tools, and session scope."""
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
    if skill_sections:
        skills_block = "## Skills\n\n" + "\n\n".join(skill_sections)

    tools_block = ""
    if include_tools_manifest and settings is not None and settings.workload_token.strip():
        tool_list = ", ".join(f"`{name}`" for name in KARTOGRAPH_SCHEMA_TOOL_NAMES)
        tools_block = f"{_TOOLS_QUICK_REFERENCE}\n\nRegistered tools: {tool_list}."

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

    sections = [
        section
        for section in (
            system_prompt,
            guardrail_lines,
            skills_block,
            tools_block,
            session_block,
            workspace_appendix.strip(),
        )
        if section
    ]
    return "\n\n".join(sections) or "You are the Graph Management Assistant."
