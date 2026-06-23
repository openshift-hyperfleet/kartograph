"""Scope helpers for Graph Management Assistant sessions."""

from __future__ import annotations

from extraction.domain.value_objects import ExtractionSessionMode, GraphManagementUiMode


def resolve_backend_session_mode(
    ui_mode: GraphManagementUiMode,
) -> ExtractionSessionMode:
    """Map graph-management UI mode to extraction session backend mode."""
    if ui_mode == GraphManagementUiMode.INITIAL_SCHEMA_DESIGN:
        return ExtractionSessionMode.SCHEMA_BOOTSTRAP
    return ExtractionSessionMode.EXTRACTION_OPERATIONS
