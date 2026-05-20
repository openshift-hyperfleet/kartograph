"""Skill resolution for extraction sessions."""

from __future__ import annotations

from dataclasses import dataclass

from extraction.domain.value_objects import ExtractionSessionMode
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
            "You are the schema bootstrap guide. Start by understanding the user's "
            "capabilities, goals, and domain intent before proposing a graph model."
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
        ),
    },
}

_GLOBAL_SKILL_TEMPLATES: dict[ExtractionSessionMode, dict[str, str]] = {
    ExtractionSessionMode.SCHEMA_BOOTSTRAP: {
        "capabilities_intake": (
            "Begin by asking for user capabilities/goals and confirm whether they "
            "want a first-pass schema attempt or guided co-design."
        ),
        "schema_modeling": (
            "Guide the user to define complete entity and relationship types "
            "with clear labels, constraints, and required properties."
        ),
        "prepopulation_validation": (
            "Prioritize prepopulated type coverage and highlight any missing "
            "instances required before extraction-mode transition."
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

