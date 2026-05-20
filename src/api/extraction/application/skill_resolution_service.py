"""Skill resolution for extraction sessions."""

from __future__ import annotations

from extraction.domain.value_objects import ExtractionSessionMode
from extraction.ports.repositories import IExtractionSkillOverrideRepository


_GLOBAL_SKILL_TEMPLATES: dict[ExtractionSessionMode, dict[str, str]] = {
    ExtractionSessionMode.SCHEMA_BOOTSTRAP: {
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
    ) -> dict[str, str]:
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

        return resolved

