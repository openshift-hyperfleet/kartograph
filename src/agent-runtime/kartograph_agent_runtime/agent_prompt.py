"""System prompt assembly for the Graph Management Assistant."""

from __future__ import annotations

from typing import Any, Literal

PromptDetail = Literal["full", "compact"]

from kartograph_agent_runtime.extraction_jobs_tools import KARTOGRAPH_EXTRACTION_JOBS_TOOL_NAMES
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
| `Write` | Create scanner scripts and JSON outputs under `instance_generators/` |
| `Edit` | Update existing workspace files (e.g. refine a scanner script) |
| `Grep` | Search file contents in `repository-files/<data_source>/` |
| `Glob` | List files by pattern for instance generation |
| `Bash` | Run scanners and `preview_instances.py` against `repository-files/` |

See `instance_generators/PREPOPULATION_WORKFLOW.md` for the numbered prepopulation checklist.

### Quick workflow

1. `kartograph_get_schema_authoring_guide`
2. `kartograph_get_workspace_readiness`
3. `kartograph_get_schema_ontology`
4. Prepopulation: `{Label}.py` (case-sensitive) → `out/{Label}_instances.json` → `preview_instances.py` → `entities_to_jsonl.py` → apply-from-file
5. Model types → `kartograph_save_schema_ontology`
6. Apply CREATE mutations → `kartograph_apply_graph_mutations` (small fixes inline; bulk via generator output)
7. Create relationship edges after entity IDs are known
8. Verify with `kartograph_list_instances_by_type` and `kartograph_get_workspace_readiness`

### Failure modes (stop prepopulation on infra errors)

- **422** — fix ontology or JSONL; retry is appropriate.
- **500/503 on readiness or apply after validate passed** — platform/graph storage issue; **stop**, report to the operator, do not advance to the next prepopulated label. Suggest `make dev-repair-age-graphs` in local dev.
- **`approved_at: null`** — optional; does **not** block prepopulation.
- **Validate pass + apply 500/503** — backend bug; report both outcomes; do not skip to the next entity type.

Start prepopulation only when schema save succeeded **and** readiness returns 200 with gaps.

Writes persist to the platform database for the active knowledge graph.
""".strip()

_EXTRACTION_JOBS_TOOLS_REFERENCE = """
## Extraction job tools (extraction-jobs UI mode)

| Tool | Purpose |
|------|---------|
| `kartograph_get_extraction_jobs_config` | Read saved job sets, live instance counts, and `relationship_authoring_by_entity_type` |
| `kartograph_save_extraction_jobs_config` | Save job sets and regenerate pending jobs (operator-approved configs) |
| `kartograph_get_extraction_jobs_plan_summary` | Projected job counts per job set before/after save |
| `kartograph_get_extraction_jobs_status` | Queue metrics: pending/in-progress/completed/failed jobs |

When the operator approves a job set proposal, call `kartograph_save_extraction_jobs_config` —
do not ask them to manually fill the extraction-jobs form.

### Per-instance description (by_instances job sets)

Before drafting, call `kartograph_get_extraction_jobs_config` and read
`entity_type_authoring_context.{EntityType}` for exact property names plus
`relationship_authoring_by_entity_type.{EntityType}` — it lists exact `owned` line prefixes
and `ignored` ignore_line text from live instance counts and the real ontology. Copy those lines;
do not invent relationship labels or property names from memory.

Use this template (substitute real entity and relationship names):

```
For each of the instances of {EntityType} you've been assigned, capture everything into the knowledge graph: all properties of that instance and every relationship instance this job set owns (see lines below).

Properties:
- {property_name}: {how to extract, where in repository-files/, value shape}
- ...

{EntityType} -> {relationship_label} -> {CounterpartType}: {when to create/update; how to resolve counterpart slug}
(one line per entry in relationship_authoring_by_entity_type.{EntityType}.owned only)

Ignore these relationships:
IGNORE {EntityType} -> {relationship_label} -> {CounterpartType}: handled by {CounterpartType} job sets ({counterpart_count} vs {EntityType} {entity_count} instances). Do not create or update this edge in this job set.
(one line per entry in relationship_authoring_by_entity_type.{EntityType}.ignored — never list these as active extraction targets)

```

**Ownership rule:** include `{EntityType} -> {rel} -> {Counterpart}` as an active line only when
{EntityType} has MORE live instances than {Counterpart}. When the counterpart has more (or equal),
use an IGNORE line only — copy the exact lines from `relationship_authoring_by_entity_type`.

Do **not** use theme-only sections (Implementation Analysis, Configuration Details, etc.).
When the operator approves, save via `kartograph_save_extraction_jobs_config`.
""".strip()

_TOOLS_COMPACT_REFERENCE = (
    "Tools: kartograph_* schema MCP tools, plus Read/Write/Edit/Grep/Glob/Bash. "
    "Prepopulation: {label}.py → out/{label}_instances.json → entities_to_jsonl.py or "
    "relationships_to_jsonl.py → validate/apply out/{label}_instances.jsonl. Never /tmp."
)


def _format_workspace_readiness(readiness: dict[str, Any]) -> str:
    lines = ["## Workspace readiness (live snapshot)"]

    next_action = str(readiness.get("next_action") or "").strip()
    if next_action:
        lines.append(f"- **Next action:** {next_action}")

    entity_gaps = readiness.get("prepopulated_entity_types_without_instances_live") or []
    rel_gaps = readiness.get("prepopulated_relationship_types_without_instances_live") or []
    blocking = readiness.get("blocking_reasons") or []
    prepopulated_types = readiness.get("prepopulated_entity_types") or []
    prepopulated_relationships = readiness.get("prepopulated_relationship_types") or []
    prepopulation_tasks = readiness.get("prepopulation_tasks") or []

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

    if prepopulation_tasks:
        lines.append("- Prepopulation tasks:")
        for task in prepopulation_tasks[:8]:
            if not isinstance(task, dict):
                continue
            kind = str(task.get("kind") or "task")
            if kind == "entity":
                label = str(task.get("label") or "?")
                live = task.get("live_instance_count", 0)
                scanner = str(task.get("scanner_path") or "?")
                lines.append(f"  - `{label}` ({live} live) → create `{scanner}`")
            else:
                key = str(task.get("key") or "?")
                live = task.get("live_instance_count", 0)
                scanner = str(task.get("scanner_path") or "?")
                lines.append(f"  - `{key}` ({live} live) → create `{scanner}`")

    if prepopulated_types:
        lines.append("- Prepopulated entity coverage:")
        for row in prepopulated_types:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or "?")
            live = row.get("live_instance_count", 0)
            metadata = row.get("metadata_instance_count", 0)
            required = row.get("required_properties") or []
            req_hint = f", required={list(required)}" if required else ""
            lines.append(f"  - `{label}`: live={live}, metadata={metadata}{req_hint}")

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


_EXTRACTION_JOBS_COMPACT_SKILL_KEYS = ("per_instance_description_authoring", "job_set_contract")


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

    skills_dict = dict(skills) if isinstance(skills, dict) else {}
    if prompt_detail == "compact" and ui_mode == "extraction-jobs":
        skill_items = sorted(
            (key, value)
            for key, value in skills_dict.items()
            if key in _EXTRACTION_JOBS_COMPACT_SKILL_KEYS
        )
    elif prompt_detail == "full":
        skill_items = sorted(skills_dict.items())
    else:
        skill_items = []

    for key, value in skill_items:
        text = str(value).strip()
        if text:
            skill_sections.append(f"**{key}**: {text}")

    skills_block = ""
    if skill_sections and (prompt_detail == "full" or skill_items):
        skills_block = "## Skills\n\n" + "\n\n".join(skill_sections)

    tools_block = ""
    if include_tools_manifest and settings is not None and settings.workload_token.strip():
        if prompt_detail == "compact":
            extraction_jobs_block = (
                f"\n\n{_EXTRACTION_JOBS_TOOLS_REFERENCE}"
                if ui_mode == "extraction-jobs"
                else ""
            )
            tools_block = f"## Tools\n\n{_TOOLS_COMPACT_REFERENCE}{extraction_jobs_block}"
        else:
            kartograph_tools = ", ".join(
                f"`{name}`"
                for name in (
                    *KARTOGRAPH_SCHEMA_TOOL_NAMES,
                    *(
                        KARTOGRAPH_EXTRACTION_JOBS_TOOL_NAMES
                        if ui_mode == "extraction-jobs"
                        else ()
                    ),
                )
            )
            file_tools = ", ".join(f"`{name}`" for name in WORKSPACE_FILE_TOOL_NAMES)
            extraction_jobs_block = (
                f"\n\n{_EXTRACTION_JOBS_TOOLS_REFERENCE}"
                if ui_mode == "extraction-jobs"
                else ""
            )
            tools_block = (
                f"{_TOOLS_QUICK_REFERENCE}{extraction_jobs_block}\n\n"
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
