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
            "Start by understanding user goals, then model the ontology and apply changes "
            "with kartograph_get_schema_ontology and kartograph_save_schema_ontology."
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
            "Ask for goals once, then co-design or propose a first-pass schema."
        ),
        "schema_workflow": (
            "Call kartograph_get_schema_authoring_guide when you need shapes or mutation rules. "
            "Read/save ontology via kartograph_get_schema_ontology and kartograph_save_schema_ontology."
        ),
        "prepopulation": (
            "For prepopulated types: set instance_generator on the type when helpful, run script "
            "under instance_generators/ with Bash, convert with json_*_to_jsonl helpers, validate "
            "then apply-from-file. CREATE cannot duplicate existing instances — use UPDATE to edit. "
            "Bidirectional relationships default on: author primary-direction edges only; platform "
            "creates inverse type + twin instances. Set bidirectional=false for asymmetric edges."
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

