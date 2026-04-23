# Spec Alignment Reviewer Memory

## Entries

### 2026-04-22 | task-008 Knowledge Graphs review
**Pattern:** KG cascade delete spec says "including their encrypted credentials" but KnowledgeGraphService.delete() only calls ds_repo.delete() — which does not call secret_store.delete(). DataSourceService.delete() does call secret_store.delete(), but that service is not used in the KG cascade path.

**Action:** Flagged as PARTIAL gap. The spec says "all data sources within it are deleted (including their encrypted credentials)" but encrypted credentials are not deleted during KG cascade delete.

**Note:** Project uses MagicMock/AsyncMock in unit tests throughout (not fakes). This is consistent with IAM tests and is an established pattern, not a task-008-specific deviation.

**Context:** Permission inheritance tested via SpiceDB schema unit tests (test_schema_design.py) — validates schema expressions, not live SpiceDB behavior. No integration tests for KG permission inheritance scenarios specifically.
