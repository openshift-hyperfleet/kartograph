"""Unit tests for ExtractionSkillResolutionService."""

from __future__ import annotations

import pytest

from extraction.application.skill_resolution_service import (
    ExtractionSkillResolutionService,
)
from extraction.domain.value_objects import ExtractionSessionMode


class _InMemorySkillOverrideRepository:
    def __init__(self, overrides: dict[tuple[str, ExtractionSessionMode], dict[str, str]] | None = None) -> None:
        self._overrides = overrides or {}

    async def get_overrides_for_knowledge_graph(
        self,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
    ) -> dict[str, str]:
        return dict(self._overrides.get((knowledge_graph_id, mode), {}))


@pytest.mark.asyncio
class TestExtractionSkillResolutionService:
    async def test_bootstrap_mode_uses_bootstrap_defaults(self):
        service = ExtractionSkillResolutionService(
            override_repository=_InMemorySkillOverrideRepository()
        )

        resolved = await service.resolve_for_session(
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
        )

        assert set(resolved.skills.keys()) >= {
            "capabilities_intake",
            "bootstrap_workflow",
            "schema_modeling",
            "schema_workflow",
            "prepopulation",
            "readiness_reporting",
        }
        assert "entities_to_jsonl.py" in resolved.skills["prepopulation"]
        assert "_instances.json" in resolved.skills["prepopulation"]
        assert "Entities before relationships" in resolved.skills["prepopulation"]
        guardrails_text = " ".join(resolved.guardrails)
        assert "entities_to_jsonl.py" in guardrails_text
        assert "never /tmp" in guardrails_text or "Never /tmp" in guardrails_text
        assert "do not ask" in guardrails_text
        assert "kartograph_save_schema_ontology" in guardrails_text
        assert len(resolved.prompt_hierarchy) > 0

    async def test_extraction_mode_uses_extraction_defaults(self):
        service = ExtractionSkillResolutionService(
            override_repository=_InMemorySkillOverrideRepository()
        )

        resolved = await service.resolve_for_session(
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
        )

        assert "job_setup" in resolved.skills
        assert "per_instance_description_authoring" in resolved.skills
        assert "EntityType} ->" in resolved.skills["per_instance_description_authoring"]
        assert "MORE live instances" in resolved.skills["per_instance_description_authoring"]
        assert "Implementation Analysis" in resolved.skills["per_instance_description_authoring"]
        assert "minor_edits" in resolved.skills
        assert "schema_edits_secondary" in resolved.skills
        assert "extraction" in resolved.system_prompt.lower()
        assert len(resolved.prompt_hierarchy) > 0

    async def test_kg_overrides_replace_matching_template_and_append_new(self):
        overrides = {
            ("kg-1", ExtractionSessionMode.SCHEMA_BOOTSTRAP): {
                "prepopulation": "Custom prepopulation guidance.",
                "custom_skill": "Extra skill text.",
            }
        }
        service = ExtractionSkillResolutionService(
            override_repository=_InMemorySkillOverrideRepository(overrides)
        )

        resolved = await service.resolve_for_session(
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
        )

        assert resolved.skills["prepopulation"] == "Custom prepopulation guidance."
        assert resolved.skills["custom_skill"] == "Extra skill text."
        assert "bootstrap_workflow" in resolved.skills

    async def test_override_merge_is_deterministic(self):
        overrides = {
            ("kg-1", ExtractionSessionMode.SCHEMA_BOOTSTRAP): {"prepopulation": "A"},
            ("kg-2", ExtractionSessionMode.SCHEMA_BOOTSTRAP): {"prepopulation": "B"},
        }
        service = ExtractionSkillResolutionService(
            override_repository=_InMemorySkillOverrideRepository(overrides)
        )

        first = await service.resolve_for_session(
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
        )
        second = await service.resolve_for_session(
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
        )

        assert first.skills == second.skills
