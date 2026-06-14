"""Unit tests for schema authoring guide content."""

from __future__ import annotations

from extraction.application.schema_authoring_guide import SCHEMA_AUTHORING_GUIDE


def test_authoring_guide_documents_bootstrap_and_modeling_guidance() -> None:
    assert "## Workspace layout" in SCHEMA_AUTHORING_GUIDE
    assert "entities_to_jsonl.py" in SCHEMA_AUTHORING_GUIDE
    assert "relationships_to_jsonl.py" in SCHEMA_AUTHORING_GUIDE
    assert "_entity_scanner.example.py" in SCHEMA_AUTHORING_GUIDE
    assert "E2ETest_instances.json" in SCHEMA_AUTHORING_GUIDE or "out/{Label}_instances.json" in SCHEMA_AUTHORING_GUIDE
    assert "prepopulated" in SCHEMA_AUTHORING_GUIDE
    assert "/tmp" in SCHEMA_AUTHORING_GUIDE
    assert "data_source.py" not in SCHEMA_AUTHORING_GUIDE
    assert "## Failure modes" in SCHEMA_AUTHORING_GUIDE
    assert "approved_at" in SCHEMA_AUTHORING_GUIDE
    assert "500/503" in SCHEMA_AUTHORING_GUIDE
    assert "smoke-test" in SCHEMA_AUTHORING_GUIDE.lower() or "smoke test" in SCHEMA_AUTHORING_GUIDE.lower()
    assert "run_scanner.py" in SCHEMA_AUTHORING_GUIDE
    assert "next_action" in SCHEMA_AUTHORING_GUIDE
    assert "## Relationship types" in SCHEMA_AUTHORING_GUIDE
    assert "one row per primary relationship label" in SCHEMA_AUTHORING_GUIDE
    assert "kartograph_get_schema_ontology" in SCHEMA_AUTHORING_GUIDE
    assert "N×M separate UI rows" in SCHEMA_AUTHORING_GUIDE
    assert "source_labels[0]" in SCHEMA_AUTHORING_GUIDE or "first source" in SCHEMA_AUTHORING_GUIDE
    assert "Unique edge labels" in SCHEMA_AUTHORING_GUIDE
    assert "duplicate labels are rejected" in SCHEMA_AUTHORING_GUIDE
    assert "tests_ct_api" in SCHEMA_AUTHORING_GUIDE
    assert "eight primary" in SCHEMA_AUTHORING_GUIDE
