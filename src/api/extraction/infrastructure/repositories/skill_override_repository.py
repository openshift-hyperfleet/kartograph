"""Infrastructure repository for extraction skill overrides."""

from __future__ import annotations

from extraction.domain.value_objects import ExtractionSessionMode
from extraction.ports.repositories import IExtractionSkillOverrideRepository


class ExtractionSkillOverrideRepository(IExtractionSkillOverrideRepository):
    """Return KG-specific skill overrides.

    Current tracer-bullet implementation returns no overrides. This still allows
    the resolution service to compose deterministic mode defaults and provides a
    stable extension point for persisted KG overrides.
    """

    async def get_overrides_for_knowledge_graph(
        self,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
    ) -> dict[str, str]:
        return {}
