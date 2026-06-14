"""Extraction agent session entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from extraction.domain.value_objects import ExtractionSessionMode, GraphManagementUiMode


@dataclass
class ExtractionAgentSession:
    """Long-running conversational session scoped to user/KG/UI mode."""

    id: str
    user_id: str
    knowledge_graph_id: str
    mode: ExtractionSessionMode
    graph_management_ui_mode: GraphManagementUiMode | None = None
    message_history: list[dict[str, Any]] = field(default_factory=list)
    runtime_context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    archived_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.archived_at is None

    def archive(self, *, when: datetime | None = None) -> None:
        now = when or datetime.now(UTC)
        self.archived_at = now
        self.updated_at = now

