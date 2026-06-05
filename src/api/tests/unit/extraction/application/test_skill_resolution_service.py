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
            "schema_workflow",
            "prepopulation",
        }
        assert "six-phase" in resolved.skills["bootstrap_workflow"].lower() or "6" in resolved.skills["bootstrap_workflow"]
        assert "Workspace discovery" in resolved.skills["bootstrap_workflow"]
        assert "3–5" in resolved.skills["capabilities_intake"]
        assert "instance_generators" in resolved.skills["prepopulation"]
        assert "kartograph_get_schema_authoring_guide" in resolved.skills["schema_workflow"]
        assert "capabilities_intake" in resolved.skills
        assert "goal" in resolved.system_prompt.lower()
        assert len(resolved.prompt_hierarchy) > 0
        assert len(resolved.guardrails) > 0

    async def test_extraction_mode_uses_extraction_defaults(self):
        service = ExtractionSkillResolutionService(
            override_repository=_InMemorySkillOverrideRepository()
        )

        resolved = await service.resolve_for_session(
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
        )

        assert "job_setup" in resolved.skills
        assert "minor_edits" in resolved.skills
        assert "schema_edits_secondary" in resolved.skills
        assert "extraction" in resolved.system_prompt.lower()
        assert len(resolved.prompt_hierarchy) > 0
        assert len(resolved.guardrails) > 0

    async def test_kg_overrides_replace_matching_template_and_append_new(self):
        repo = _InMemorySkillOverrideRepository(
            overrides={
                (
                    "kg-1",
                    ExtractionSessionMode.EXTRACTION_OPERATIONS,
                ): {
                    "job_setup": "KG-specific job setup instructions",
                    "custom_review": "Custom review flow",
                }
            }
        )
        service = ExtractionSkillResolutionService(override_repository=repo)

        resolved = await service.resolve_for_session(
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
        )

        assert resolved.skills["job_setup"] == "KG-specific job setup instructions"
        assert resolved.skills["custom_review"] == "Custom review flow"

    async def test_override_merge_is_deterministic(self):
        repo = _InMemorySkillOverrideRepository(
            overrides={
                (
                    "kg-1",
                    ExtractionSessionMode.SCHEMA_BOOTSTRAP,
                ): {
                    "z_last": "z",
                    "a_first": "a",
                }
            }
        )
        service = ExtractionSkillResolutionService(override_repository=repo)

        resolved = await service.resolve_for_session(
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
        )

        # Additional override keys are merged in sorted order for determinism.
        assert list(resolved.skills.keys())[-2:] == ["a_first", "z_last"]

