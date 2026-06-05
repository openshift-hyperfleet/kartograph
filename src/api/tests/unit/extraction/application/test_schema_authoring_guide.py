"""Unit tests for schema authoring guide content."""

from __future__ import annotations

from extraction.application.schema_authoring_guide import SCHEMA_AUTHORING_GUIDE


def test_authoring_guide_documents_six_phase_bootstrap_workflow() -> None:
    assert "## Bootstrap workflow (6 phases)" in SCHEMA_AUTHORING_GUIDE
    assert "Understand goals" in SCHEMA_AUTHORING_GUIDE
    assert "Workspace discovery" in SCHEMA_AUTHORING_GUIDE
    assert "Save ontology" in SCHEMA_AUTHORING_GUIDE
    assert "Implement prepopulation" in SCHEMA_AUTHORING_GUIDE
