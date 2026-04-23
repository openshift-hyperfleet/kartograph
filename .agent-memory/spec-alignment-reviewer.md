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

### 2026-04-23 | task-008 Knowledge Graphs full spec alignment review — PASS (confirmed stable)
**Pattern:** All 6 SHALL requirements and 11 scenarios verified against implementation. No deviations found. Implementation stable across multiple review cycles.

**Action:** Verdict PASS. Wrote detailed per-requirement coverage report to worker-result.yaml.

**Context:** Key architectural patterns to recognize as correct (not deviations): (1) list_for_workspace uses workspace VIEW check + SpiceDB read_relationships rather than per-KG VIEW checks — valid because workspace VIEW implies KG VIEW via schema inheritance; (2) outbox pattern for SpiceDB writes at create time (not inline in service) is intentional; (3) AsyncMock in unit tests (not fakes) is established project pattern.

### 2026-04-23 | task-008 final spec alignment gate — PASS (gate 7 verified)
**Pattern:** GET /management/knowledge-graphs (tenant-visible list) was the outstanding CodeRabbit concern. Commit 4fd5c66f added TestListAllKnowledgeGraphs (4 unit tests). Service list_all() verified: fetches by tenant, filters per-KG VIEW check. Route confirmed implemented. 334 management unit tests pass.

**Action:** Verdict PASS confirmed. worker-result.yaml updated with per-requirement COVERED status for all 6 requirements and 11 scenarios.

**Context:** This was gate 7 (spec alignment) running after code review (gate 6). The prior worker-result.yaml had a code review verdict — this pass rewrites it with spec alignment findings. No code changes made — read-only review.

### 2026-04-23 | task-008 independent re-verification of PR feedback items — PASS
**Pattern:** Two MAJOR PR feedback items independently verified as resolved.

**Action:** (1) ParentWorkspaceNotFoundError and ParentWorkspaceCrossTenantError confirmed present in iam/ports/exceptions.py lines 103-123 with docstrings. workspace_service.py raises them at lines 165 and 171. routes.py imports both at lines 18-19, catches them in single except clause at lines 87-93, advertises 404 in OpenAPI responses map at line 57. Tests in test_workspace_service.py (lines 203, 234) and test_workspaces_routes.py (lines 198, 225) assert typed exceptions — no string parsing. (2) Architecture test test_management_does_not_import_iam uses three targeted exclusions: management.presentation.knowledge_graphs.routes*, management.presentation.knowledge_graphs, management.presentation — NOT the blanket management.presentation* — confirmed in test_architecture.py lines 249-253. management.presentation.knowledge_graphs.models is NOT excluded. 2066 unit tests pass.

**Context:** All spec requirements verified. No deviations found in this independent pass.
