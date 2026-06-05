"""Skill resolution for extraction sessions."""

from __future__ import annotations

from dataclasses import dataclass

from extraction.domain.value_objects import ExtractionSessionMode, GraphManagementUiMode
from extraction.ports.repositories import IExtractionSkillOverrideRepository


@dataclass(frozen=True)
class ResolvedExtractionSkillPack:
    """Resolved mode-aware prompt bundle for agent runtime."""

    system_prompt: str
    prompt_hierarchy: tuple[str, ...]
    guardrails: tuple[str, ...]
    skills: dict[str, str]


_GLOBAL_PROMPT_SETTINGS: dict[ExtractionSessionMode, dict[str, object]] = {
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
                "For bulk prepopulation never hand-author CREATE ids in chat. Use Bash generators → "
                "json_*_to_jsonl.py → validate-from-file → apply-from-file. On ontology save errors, "
                "read kartograph_get_schema_ontology and kartograph_get_schema_authoring_guide, merge "
                "a fix, then retry once."
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
            "(4) Prepopulation planning — which types/relationships are prepopulated vs manual. "
            "(5) Save ontology — kartograph_save_schema_ontology only after user confirms the full schema. "
            "(6) Implement prepopulation — generators → json_*_to_jsonl → validate-from-file → "
            "apply-from-file; entities first, then edges; verify with kartograph_get_workspace_readiness."
        ),
        "schema_modeling": (
            "Property vs entity: distinguish/categorize → property on an existing type; "
            "track which/what or needs relationships → entity type + edges. "
            "Relationships default bidirectional — author primary direction only; platform creates "
            "inverse type + twin instances. Set bidirectional=false for asymmetric edges "
            "(depends_on, created_by). For asymmetric edges, confirm X → rel → Y direction explicitly."
        ),
        "schema_workflow": (
            "Call kartograph_get_schema_authoring_guide when you need shapes, phases, or mutation rules. "
            "Read/save ontology via kartograph_get_schema_ontology and kartograph_save_schema_ontology."
        ),
        "prepopulation": (
            "Before prepopulation planning: Glob/Grep repository-files/ and cite counts from the workspace "
            "appendix. Write scripts/JSON/JSONL only under instance_generators/ (repository-files/ is "
            "read-only). For prepopulated types: run script with Bash, convert with json_*_to_jsonl, "
            "validate then apply-from-file. Bidirectional edges: primary direction only in generators."
        ),
        "readiness_reporting": (
            "After schema or prepopulation work, call kartograph_get_workspace_readiness and cite "
            "blocking_reasons, prepopulated gaps, and transition_eligible in your reply."
        ),
    },
    ExtractionSessionMode.EXTRACTION_OPERATIONS: {
        "job_setup": (
            "Prioritize extraction job setup, file-targeting strategy, and "
            "safe incremental mutation planning."
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
            "Focus on extraction job setup, JobPackage-aware file targeting, and "
            "incremental sync planning."
        ),
    },
    GraphManagementUiMode.ONE_OFF_MUTATIONS: {
        "ui_mode_framing": (
            "Focus on scoped one-off graph mutations with mutation-log auditability."
        ),
    },
}


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
        return ResolvedExtractionSkillPack(
            system_prompt=base.system_prompt,
            prompt_hierarchy=base.prompt_hierarchy,
            guardrails=base.guardrails,
            skills=merged_skills,
        )
