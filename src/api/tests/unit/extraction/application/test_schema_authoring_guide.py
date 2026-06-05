"""Unit tests for schema authoring guide content."""

from __future__ import annotations

from extraction.application.schema_authoring_guide import SCHEMA_AUTHORING_GUIDE


def test_authoring_guide_documents_bootstrap_and_modeling_guidance() -> None:
    assert "## Bootstrap workflow (6 phases)" in SCHEMA_AUTHORING_GUIDE
    assert "## Schema modeling rules" in SCHEMA_AUTHORING_GUIDE
    assert "## Workspace discovery patterns" in SCHEMA_AUTHORING_GUIDE
    assert "read-only" in SCHEMA_AUTHORING_GUIDE
    assert "Property vs entity" in SCHEMA_AUTHORING_GUIDE
    assert "Never hand-author bulk CREATE ids" in SCHEMA_AUTHORING_GUIDE
    assert "## Prepopulation execution (default)" in SCHEMA_AUTHORING_GUIDE
    assert "Prepopulation is script writing" in SCHEMA_AUTHORING_GUIDE
    assert "do not ask whether to proceed" in SCHEMA_AUTHORING_GUIDE
    assert "all" in SCHEMA_AUTHORING_GUIDE and "entity" in SCHEMA_AUTHORING_GUIDE
    assert "creatively" in SCHEMA_AUTHORING_GUIDE
