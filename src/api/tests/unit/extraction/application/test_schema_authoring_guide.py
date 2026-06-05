"""Unit tests for schema authoring guide content."""

from __future__ import annotations

from extraction.application.schema_authoring_guide import SCHEMA_AUTHORING_GUIDE


def test_authoring_guide_documents_bootstrap_and_modeling_guidance() -> None:
    assert "## Workspace layout" in SCHEMA_AUTHORING_GUIDE
    assert "entities_to_jsonl.py" in SCHEMA_AUTHORING_GUIDE
    assert "relationships_to_jsonl.py" in SCHEMA_AUTHORING_GUIDE
    assert "_entity_scanner.example.py" in SCHEMA_AUTHORING_GUIDE
    assert "test_instances.json" in SCHEMA_AUTHORING_GUIDE
    assert "prepopulated" in SCHEMA_AUTHORING_GUIDE
    assert "/tmp" in SCHEMA_AUTHORING_GUIDE
    assert "data_source.py" not in SCHEMA_AUTHORING_GUIDE
