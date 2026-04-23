# Spec Alignment Reviewer Memory

## Entries

### 2026-04-22 | task-008 Knowledge Graphs review
**Pattern:** KG cascade delete spec says "including their encrypted credentials" but KnowledgeGraphService.delete() only calls ds_repo.delete() — which does not call secret_store.delete(). DataSourceService.delete() does call secret_store.delete(), but that service is not used in the KG cascade path.

**Action:** Flagged as PARTIAL gap. The spec says "all data sources within it are deleted (including their encrypted credentials)" but encrypted credentials are not deleted during KG cascade delete.

**Note:** Project uses MagicMock/AsyncMock in unit tests throughout (not fakes). This is consistent with IAM tests and is an established pattern, not a task-008-specific deviation.

**Context:** Permission inheritance tested via SpiceDB schema unit tests (test_schema_design.py) — validates schema expressions, not live SpiceDB behavior. No integration tests for KG permission inheritance scenarios specifically.

### 2026-04-23 | task-008 Knowledge Graphs re-review — credential gap RESOLVED
**Pattern:** The previously flagged credential deletion gap has been resolved. `KnowledgeGraphService.delete()` now calls `secret_store.delete(path, tenant_id)` for each DS with a `credentials_path` inside the cascade transaction. Dedicated test `test_delete_cascades_encrypted_credentials` verifies this.

**Action:** Verdict updated to PASS. No gaps remain.

**Context:** Authorization relationships at create time are established via outbox pattern (ManagementEventTranslator), not inline in the service. This is the correct architectural approach for the project. SpiceDB relationship cleanup at delete covers workspace, tenant, and all direct grants (admin/editor/viewer) via filter-based deletion. Integration tests in `test_knowledge_graph_authorization.py` cover live SpiceDB permission inheritance scenarios.
