"""Skill resolution for extraction sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from extraction.domain.value_objects import ExtractionSessionMode, GraphManagementUiMode
from extraction.ports.repositories import IExtractionSkillOverrideRepository


@dataclass(frozen=True)
class ResolvedExtractionSkillPack:
    """Resolved mode-aware prompt bundle for agent runtime."""

    system_prompt: str
    prompt_hierarchy: tuple[str, ...]
    guardrails: tuple[str, ...]
    skills: dict[str, str]


_GLOBAL_PROMPT_SETTINGS: dict[ExtractionSessionMode, dict[str, Any]] = {
    ExtractionSessionMode.SCHEMA_BOOTSTRAP: {
        "system_prompt": (
            "You are the Graph Management Assistant for schema bootstrap. "
            "Use Kartograph schema tools to read and write entity/relationship types "
            "and instances — do not discover or call raw HTTP API routes. "
            "Follow the six-phase bootstrap workflow (goals → discovery → schema Q&A → "
            "prepopulation planning → confirmed ontology save → bulk implementation). "
            "Do not conflate schema design, prepopulation planning, and implementation."
        ),
        "prompt_hierarchy": (
            "platform_security_constraints",
            "tenant_and_knowledge_graph_scope",
            "schema_bootstrap_goals_and_capabilities_intake",
            "mode_specific_skill_pack",
        ),
        "guardrails": (
            "Prefer mutation-log compatible schema guidance over ad-hoc writes.",
            "Never fabricate repository content or credentials.",
            "Keep recommendations scoped to the active knowledge graph.",
            "Use kartograph_* schema tools for ontology and JSONL mutations; never probe /management or /graph HTTP routes manually.",
            "Format user-facing replies in GitHub-flavored Markdown (headings, lists, fenced code blocks, tables) for readability in the chat UI.",
            (
                "When the user gives multiple deliverables in one message (three or more bullets, "
                "or any mix of ontology edits + bulk prepopulation + relationships), do not execute "
                "the full list in one turn. Complete one phase only, summarize what finished, then "
                "ask whether to continue through the rest automatically or one phase at a time. "
                "Default to one phase per turn unless the user explicitly requests doing everything."
            ),
            (
                "Bootstrap phases (in order): (1) ontology/types/properties, (2) entity instances "
                "in dependency order, (3) relationship instances, (4) readiness verification via "
                "kartograph_get_workspace_readiness. Stop after each phase when multiple deliverables "
                "were requested."
            ),
            (
                "Do not call kartograph_save_schema_ontology until the user confirms the full "
                "proposed schema (types, properties, relationship directions, prepopulation flags). "
                "Exception: the user explicitly says to save/apply or continues after reviewing your draft."
            ),
            (
                "Prepopulation (prepopulated=true types): copy _entity_scanner.example.py to "
                "instance_generators/{Label}.py (case-sensitive) → "
                "`python3 instance_generators/run_scanner.py {Label} --entity` (or manual JSONL pipeline) "
                "→ kartograph_apply_graph_mutations_from_file with printed jsonl_path. Apply pre-validates; "
                "validate is optional dry run. Use apply response next_action to chain labels. "
                "Never /tmp. All entity gaps before relationship gaps."
            ),
            (
                "Single prepopulation deliverable (one entity or relationship type): execute the full "
                "PREPOPULATION_WORKFLOW.md pipeline end-to-end without stopping for permission. "
                "Multiple deliverables in one message: one label per turn, summarize, then continue."
            ),
            (
                "When readiness shows prepopulated gaps after schema save, execute immediately — do not ask "
                "permission — but only after kartograph_get_workspace_readiness returns 200 with gaps. "
                "If readiness or apply returns 500/503 while validation passed, stop prepopulation, report "
                "a platform/infrastructure issue, and do not advance to the next label. "
                "One label per turn unless the user requested a single type only (then finish fully). "
                "Use readiness next_action and prepopulation_tasks for the suggested scanner path. "
                "Only ask when discovery strategy is ambiguous or strict CREATE reports duplicates."
            ),
            (
                "approved_at on saved ontology is optional metadata; null does not block prepopulation. "
                "Do not treat missing approved_at as schema activation failure."
            ),
            (
                "If kartograph_validate_graph_mutations_from_file passes and apply-from-file returns "
                "500/503, report both outcomes as a backend bug — do not retry blindly or continue to "
                "the next prepopulated type."
            ),
            (
                "Relationship ontology UI rows require unique edge_types labels. When the user asks "
                "for multiple source→target pairs (e.g. eight ComponentTest/E2ETest tests rows), save "
                "one primary edge_types entry per pair with distinct labels — never reuse the same "
                "label six times. After kartograph_save_schema_ontology, call kartograph_get_schema_ontology "
                "and report the stored primary label count before telling the user to refresh the UI."
            ),
        ),
    },
    ExtractionSessionMode.EXTRACTION_OPERATIONS: {
        "system_prompt": (
            "You are the extraction operations guide. Optimize for safe incremental "
            "job setup, scoped maintenance, and auditable mutation outcomes."
        ),
        "prompt_hierarchy": (
            "platform_security_constraints",
            "tenant_and_knowledge_graph_scope",
            "extraction_operations_objective",
            "mode_specific_skill_pack",
        ),
        "guardrails": (
            "All write paths must remain mutation-log auditable.",
            "Treat schema edits as secondary unless explicitly requested.",
            "Avoid broad destructive changes without explicit confirmation.",
            "Format user-facing replies in GitHub-flavored Markdown (headings, lists, fenced code blocks, tables) for readability in the chat UI.",
        ),
    },
}

_GLOBAL_SKILL_TEMPLATES: dict[ExtractionSessionMode, dict[str, str]] = {
    ExtractionSessionMode.SCHEMA_BOOTSTRAP: {
        "capabilities_intake": (
            "Phase 1 — Understand goals: ask what questions the graph must answer; collect "
            "3–5 concrete stakeholder use cases before proposing types."
        ),
        "bootstrap_workflow": (
            "Opinionated schema bootstrap phases (complete in order; one phase per turn when "
            "the user gave multiple deliverables): "
            "(1) Understand goals — 3–5 questions the graph must answer. "
            "(2) Workspace discovery — Glob/Grep on repository-files/, cite file counts and patterns. "
            "(3) Draft schema + Q&A — propose types/properties/relationships; show workspace examples. "
            "(4) Prepopulation planning — which types/relationships are prepopulated vs manual (during "
            "schema design only; do not re-ask once schema is saved). "
            "(5) Save ontology — kartograph_save_schema_ontology only after user confirms the full schema. "
            "(6) Implement prepopulation — one prepopulated label per turn via {label}.py → "
            "{label}_instances.json(l) → apply-from-file; all entities before relationships."
        ),
        "schema_modeling": (
            "Property vs entity: distinguish/categorize → property on an existing type; "
            "track which/what or needs relationships → entity type + edges. "
            "Edge type labels must be UNIQUE — never duplicate `tests` or `covered_by` across rows. "
            "When the operator wants N Relationship ontology UI rows (one per source→target pair), "
            "author N primary edge_types with N distinct labels (e.g. tests_ct_api, covered_by_us_e2e), "
            "each with a single source_labels/target_labels pair and distinct inverse_label when "
            "bidirectional. Relationship scanners use --rel matching the saved label. "
            "Relationships default bidirectional — one primary entry per unique label; never add a "
            "separate inverse type (platform auto-generates it). UI: one row per primary label. "
            "After save, read kartograph_get_schema_ontology and confirm primary edge type count — "
            "never claim N types saved until read-back shows N distinct primary labels. "
            "Set bidirectional=false only for asymmetric edges (depends_on, created_by). "
            "Full rules: kartograph_get_schema_authoring_guide."
        ),
        "schema_workflow": (
            "Call kartograph_get_schema_authoring_guide when you need shapes, phases, or mutation rules. "
            "Read/save ontology via kartograph_get_schema_ontology and kartograph_save_schema_ontology."
        ),
        "prepopulation": (
            "Follow instance_generators/PREPOPULATION_WORKFLOW.md. Per gap: {Label}.py (case-sensitive) "
            "→ `run_scanner.py {Label} --entity` (preferred) or manual entities_to_jsonl.py → "
            "apply-from-file. Relationships: run_scanner.py --relationship --source --rel --target. "
            "Readiness prepopulation_tasks include order, blocking_types, run_command, and underscore "
            "output paths. Apply response includes next_action and remaining gaps. "
            "preview_instances.py: use for smoke test or 50–500 instance spot-checks. "
            "Entities before relationships. Stop on 500/503 after validate passed."
        ),
        "readiness_reporting": (
            "After schema or prepopulation work, call kartograph_get_workspace_readiness and cite "
            "next_action, prepopulation_tasks, blocking_reasons, and transition_eligible. When gaps remain "
            "after schema save, state which single prepopulation task you are executing next — do not poll "
            "the user for permission to start unless the user asked for multiple types at once. "
            "If readiness returns 500/503, stop prepopulation and report infrastructure failure — do not "
            "interpret approved_at=null as the cause."
        ),
        "failure_modes": (
            "422 = fix ontology or JSONL. 500/503 on readiness or apply after validate passed = platform "
            "graph storage issue — stop, report, suggest dev repair; do not continue to next label. "
            "approved_at null is allowed. Validation success means apply should work unless the server fails."
        ),
    },
    ExtractionSessionMode.EXTRACTION_OPERATIONS: {
        "job_setup": (
            "Prioritize extraction job set authoring: by_instances batches with required "
            "per-instance extraction descriptions (no separate extraction_plan.md). "
            "Each description tells the extraction worker what to enrich for assigned entity slugs. "
            "Follow per_instance_description_authoring — all properties on the target type; "
            "relationship lines only where that type has more live instances than the counterpart. "
            "When the operator approves "
            "a proposed configuration, persist it yourself with "
            "kartograph_save_extraction_jobs_config — never instruct them to manually enter "
            "values in the extraction-jobs UI."
        ),
        "per_instance_description_authoring": (
            "The job set `description` is the shared per-instance brief for every by_instances job. "
            "Before drafting, call kartograph_get_schema_ontology and "
            "kartograph_get_extraction_jobs_config. Read "
            "entity_type_authoring_context.{EntityType}.properties for the exact property "
            "names and relationship_authoring_by_entity_type.{EntityType} for owned/ignored "
            "relationship lines derived from live instance counts and the real ontology — "
            "never invent relationship labels or property names. "
            "Compare counts numerically for every ontology relationship before writing each line. "
            "Write the description using this exact shape (replace with real ontology names — "
            "never use placeholder EntityX in saved text): "
            "Opening (one paragraph): 'For each of the instances of {EntityType} you've been "
            "assigned, capture everything into the knowledge graph: all properties of that "
            "instance and every applicable relationship instance this job set owns (see lines "
            "below).' "
            "Then 'Properties:' — list each property on {EntityType} by name; under it give "
            "extraction instructions (source files, value shape, defaults). Call out special "
            "handling inline per property when needed (enums, secrets, derived values). "
            "Then one line per relationship type this job set owns (after applying the "
            "instance-count rule), formatted exactly: "
            "'{EntityType} -> {relationship_label} -> {CounterpartType}: ' followed by when to "
            "create or update that edge, how to resolve the counterpart slug, and whether to "
            "create missing endpoints. "
            "Then 'Ignore these relationships:' — for every ontology edge involving {EntityType} "
            "where {EntityType} has fewer or equal live instances than the counterpart, write "
            "exactly one line: "
            "'IGNORE {EntityType} -> {relationship_label} -> {CounterpartType}: handled by "
            "{CounterpartType} job sets ({counterpart_count} vs {EntityType} {entity_count} "
            "instances). Do not create or update this edge in this job set.' "
            "List every such edge explicitly; never leave ignored relationships unstated. "
            "FORBIDDEN: thematic sections only (e.g. 'Implementation Analysis', 'Configuration "
            "Details', 'Operational Characteristics') that do not name every property and every "
            "included 'Entity -> rel -> Entity' line. Narrow scope only when the operator "
            "explicitly excludes named properties or relationship types."
        ),
        "job_set_contract": (
            "Use kartograph_get_extraction_jobs_config before editing and "
            "kartograph_save_extraction_jobs_config to persist job sets for this knowledge graph. "
            "Each set needs: name, enabled (default true), strategy (by_instances primary), "
            "entity_type, instances_per_job, and description. Disabled sets are kept in config "
            "but excluded from the job queue. Saving syncs pending jobs for enabled sets only and "
            "can be done while other jobs are running. "
            "Use kartograph_get_extraction_jobs_plan_summary to cite projected job counts. "
            "Job sets run sequentially; jobs within a set run concurrently up to worker count."
        ),
        "minor_edits": (
            "Allow focused direct graph edits while preserving mutation-log "
            "auditability and schema consistency."
        ),
        "schema_edits_secondary": (
            "Keep schema edits available but framed as secondary to "
            "extraction and maintenance operations."
        ),
    },
}


_UI_MODE_SKILL_OVERLAYS: dict[GraphManagementUiMode, dict[str, str]] = {
    GraphManagementUiMode.INITIAL_SCHEMA_DESIGN: {
        "ui_mode_framing": (
            "Focus on schema bootstrap: entity/relationship modeling, intake, and "
            "prepopulation guidance before extraction jobs. Use Kartograph schema tools "
            "to persist types — do not guess API endpoints."
        ),
    },
    GraphManagementUiMode.EXTRACTION_JOBS: {
        "ui_mode_framing": (
            "Focus on extraction job set setup: by_instances batches whose description follows "
            "per_instance_description_authoring (all properties; owned relationship lines plus "
            "explicit IGNORE lines where counterpart types have more instances — e.g. Adapter "
            "includes operates_on->Resource and IGNORE verifies_inverse->ComponentTest). Persist via "
            "kartograph_save_extraction_jobs_config when the operator "
            "approves, then guide them to Run extraction. Use kartograph_get_schema_ontology and "
            "kartograph_list_instances_by_type to size batches. JobPackage readiness still "
            "applies when file-backed context is required."
        ),
    },
    GraphManagementUiMode.ONE_OFF_MUTATIONS: {
        "ui_mode_framing": (
            "Primary mode: scoped one-off graph edits executed by you in this chat. "
            "Implement schema changes via kartograph_save_schema_ontology and instance changes "
            "via validate-then-apply JSONL mutation tools. Do not defer to extraction jobs or "
            "bulk prepopulation scanners unless the operator explicitly asks."
        ),
        "intake_and_classification": (
            "Classify each request: (A) schema edit — node_types/edge_types/properties; "
            "(B) instance edit — CREATE/UPDATE/DELETE nodes or edges; (C) mixed — schema first "
            "then instances; (D) read-only — search/list/explain. Ask at most one clarifying "
            "question when slug, id, or property target is ambiguous."
        ),
        "schema_edit_workflow": (
            "Schema edits: (1) kartograph_get_schema_ontology — read current state; "
            "(2) propose delta in chat; (3) confirm unless operator said apply/save; "
            "(4) kartograph_save_schema_ontology with full merged payload; "
            "(5) read-back verify. Never use JSONL DEFINE for ontology — save tool only. "
            "Unique edge_types labels; one primary direction per label."
        ),
        "instance_edit_workflow": (
            "Instance edits (small, ≤5 lines): (1) kartograph_get_schema_ontology; "
            "(2) kartograph_list_instances_by_type or kartograph_search_graph_by_slug; "
            "(3) prefer UPDATE for existing slugs; "
            "(4) kartograph_validate_graph_mutations then kartograph_apply_graph_mutations; "
            "(5) verify affected slugs. For 5+ instances use bulk_instance_edit_workflow instead."
        ),
        "bulk_instance_edit_workflow": (
            "Bulk instance ops (5+ creates/updates/deletes): mental model — classify what to "
            "delete vs create → query once per entity type → generate JSONL in batch → validate "
            "once → apply once → report. (1) kartograph_list_instances_by_type per affected "
            "type (returns mutation-ready id + slug; paginate with offset until total covered); "
            "filter by data_source_id, slug, or properties in code — never kartograph_search_graph_by_slug "
            "per instance. (2) Generate ALL DELETE/CREATE/UPDATE lines via helpers/sync_instances.py "
            "(current vs desired JSON snapshots) or Bash/python Write to helpers/bulk_<task>.jsonl "
            "— never hand-type JSONL line-by-line. "
            "(3) kartograph_validate_graph_mutations_from_file once → "
            "kartograph_apply_graph_mutations_from_file once. (4) One list call to verify counts. "
            "Target 2–4 tool rounds total for cleanup/replace tasks."
        ),
        "jsonl_shape_reference": (
            "Every JSONL line needs op (CREATE|UPDATE|DELETE) and type (node|edge). "
            "Use set_properties (not properties). UPDATE/DELETE require top-level id. "
            "CREATE nodes need label, id, set_properties with slug, name, data_source_id."
        ),
        "confirmation_policy": (
            "Auto-apply after validate when operator said apply/fix/update/delete/replace/cleanup "
            "or change is a single non-destructive UPDATE. Confirm before schema type removal "
            "or DELETE when operator intent is ambiguous. Bulk DELETE/Cleanup explicitly requested "
            "does not need a second confirm — validate once, apply once. Never apply without validate passing."
        ),
        "session_reporting": (
            "After successful apply, report operation counts, affected slugs/labels, and any "
            "follow-up needed. End with write op summary."
        ),
    },
}


_ONE_OFF_MUTATIONS_SYSTEM_PROMPT = (
    "You are the Graph Management Assistant in One-off Mutations mode. "
    "The operator requests specific schema or instance changes; you implement them yourself "
    "using Kartograph schema tools with validate-then-apply mutation workflow. "
    "Default mental model for instance work: classify what to delete vs create → "
    "list/query once per type for ids → generate JSONL in batch (script or file) → "
    "validate once → apply once → report. Avoid per-instance search/validate/apply loops."
)

_ONE_OFF_MUTATIONS_GUARDRAILS: tuple[str, ...] = (
    "Implement requested edits in-session via kartograph_* tools; do not ask the operator to paste JSONL manually.",
    "Validate before every apply; report validation errors verbatim.",
    "Prefer UPDATE over CREATE for existing slugs; strict CREATE rejects duplicate ids/slugs.",
    "For 5+ instance changes: batch with list_instances_by_type + file-based validate/apply — never iterate per-instance tool calls.",
    "Use kartograph_list_instances_by_type for DELETE targets (returns id); do not call search_by_slug once per slug.",
    "Generate JSONL programmatically (Bash/python or Write helpers/bulk_*.jsonl); validate once, apply once.",
    "Do not start prepopulation scanners or run_scanner.py unless the operator explicitly requests bulk import.",
    "DELETE on nodes cascades edges — still use batch JSONL when operator asked to remove many instances.",
    "Schema saves require confirmation unless the operator explicitly approved.",
    "Route ongoing enrichment pipelines to Extraction Jobs mode; route greenfield ontology design to Initial Schema Design.",
)


class ExtractionSkillResolutionService:
    """Resolve session skills from global templates + KG overrides."""

    def __init__(self, override_repository: IExtractionSkillOverrideRepository) -> None:
        self._override_repository = override_repository

    async def resolve_for_session(
        self,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
    ) -> ResolvedExtractionSkillPack:
        prompt_settings = _GLOBAL_PROMPT_SETTINGS[mode]
        base_templates = dict(_GLOBAL_SKILL_TEMPLATES[mode])
        overrides = await self._override_repository.get_overrides_for_knowledge_graph(
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
        )

        resolved = dict(base_templates)

        # Merge existing keys first, then append new override keys in sorted order
        # to ensure deterministic ordering across runs.
        for key in sorted(overrides.keys()):
            if key in resolved:
                resolved[key] = overrides[key]
        for key in sorted(overrides.keys()):
            if key not in resolved:
                resolved[key] = overrides[key]

        return ResolvedExtractionSkillPack(
            system_prompt=str(prompt_settings["system_prompt"]),
            prompt_hierarchy=tuple(prompt_settings["prompt_hierarchy"]),
            guardrails=tuple(prompt_settings["guardrails"]),
            skills=resolved,
        )

    async def resolve_for_graph_management_turn(
        self,
        *,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
        ui_mode: GraphManagementUiMode,
    ) -> ResolvedExtractionSkillPack:
        """Resolve base session skills plus graph-management UI mode overlay."""
        base = await self.resolve_for_session(
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
        )
        overlay = dict(_UI_MODE_SKILL_OVERLAYS.get(ui_mode, {}))
        merged_skills = dict(base.skills)
        merged_skills.update(overlay)
        guardrails = base.guardrails
        system_prompt = base.system_prompt
        if ui_mode == GraphManagementUiMode.ONE_OFF_MUTATIONS:
            system_prompt = _ONE_OFF_MUTATIONS_SYSTEM_PROMPT
            guardrails = base.guardrails + _ONE_OFF_MUTATIONS_GUARDRAILS
        return ResolvedExtractionSkillPack(
            system_prompt=system_prompt,
            prompt_hierarchy=base.prompt_hierarchy,
            guardrails=guardrails,
            skills=merged_skills,
        )
