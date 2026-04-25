# Spec Alignment Reviewer Memory

## Entries

### 2026-04-23 | task-031 Tenant Context Spec | PASS | All requirements covered
- Pattern: Full-flow tests (calling the real dependency function with mocks) are the preferred approach for ULID normalization verification — unit tests on `_validate_ulid` alone are insufficient; the full-flow test asserts both SpiceDB call and TenantContext carry normalized value.
- Action: Confirmed `test_normalized_ulid_used_in_spicedb_subject` is complete with 3 assertions: SpiceDB resource string uses uppercase, `result.tenant_id == valid_tenant_id.value`, and `result.tenant_id == lowercase_header.upper()`.
- Context: Implementation at `src/api/iam/dependencies/tenant_context.py`; MCP auth at `src/api/shared_kernel/middleware/mcp_api_key_auth.py` + `src/api/infrastructure/mcp_dependencies.py`.
- Key test file: `src/api/tests/unit/iam/test_tenant_context_dependency.py` (42 tests) + `src/api/tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py` (17 tests).
- MCP "Authentication failure" (401) and "Service unavailability" (503) are covered in the middleware test suite, not the tenant_context test file.
- Run: `cd src/api && uv run pytest tests/unit/iam/test_tenant_context_dependency.py tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py -v`.

### 2026-04-22 | task-001 JobPackage Shared Kernel | PASS | All requirements covered
- Pattern: Shared kernel modules tend to have comprehensive test suites organized by scenario class.
- Action: Checked all 102 tests passed; verified each spec requirement had implementation + test.
- Context: Implementation in `src/api/shared_kernel/job_package/`; tests in `src/api/tests/unit/shared_kernel/job_package/`.
- Key files: `builder.py`, `reader.py`, `value_objects.py`, `checksum.py`, `path_safety.py`.
- All tests run with `cd src/api && uv run pytest tests/unit/shared_kernel/job_package/ -v`.
- Content checksum builder computes checksum in-memory (does not use `compute_content_checksum` from `checksum.py`); both use same algorithm — not a deviation.
- Streaming note: `iter_changeset()` buffers the full ZIP entry bytes before yielding parsed lines; this is inherent to ZIP format and not a spec violation since the generator satisfies the "process without loading entire file into memory" intent at the deserialization layer.

### 2026-04-25 | bulk-loading.spec.md | PASS | All requirements implemented
- Pattern: Staging-based bulk loading splits into 5 files: strategy.py, staging.py, queries.py, indexing.py, utils.py. Test split: unit tests for partitioning in test_age_bulk_loading_strategy_partitioning.py, unit tests for staging in test_staging_table_manager.py, integration tests in test_bulk_loading.py.
- Action: Verified all 6 spec requirements (Operation Partitioning, Label Pre-Creation, Staging-Based Ingestion x2, Duplicate/Orphan Detection x2, Concurrency Safety x2) covered by implementation and tests.
- Context: Same-batch node materialization is enforced by call order in strategy.py apply_batch() (nodes created first at line 151, lookup table built inside edge create at line 293). No explicit dedicated integration test for concurrent batches, but pg_advisory_xact_lock semantics guarantee the behavior.
- Key files: src/api/graph/infrastructure/age_bulk_loading/strategy.py, staging.py, queries.py, indexing.py; src/api/tests/unit/graph/infrastructure/test_age_bulk_loading_strategy_partitioning.py (18 tests), test_staging_table_manager.py (23 tests); src/api/tests/integration/test_bulk_loading.py.
- Run: cd src/api && uv run pytest tests/unit/graph/infrastructure/test_age_bulk_loading_strategy_partitioning.py tests/unit/graph/infrastructure/test_staging_table_manager.py -v

### 2026-04-25 | workspaces.spec.md | PASS | All requirements implemented
- Pattern: Workspace features span 7 files (aggregate, service, routes, models, translator, schema.zed, repository). Key invariant: last-admin guard is in aggregate layer (workspace.py:_is_last_admin), not service layer, so it fires for both remove_member and update_member_role via aggregate methods.
- Action: Verified all 9 requirements and 20+ scenarios. Unit tests (975 pass) + integration tests cover full vertical slice.
- Context: "Unauthorized creation returns 404" (not 403) is explicitly spec-compliant per routes.py:82-88. Group member listing uses read_relationships (not lookup_subjects) to avoid expansion. creator_tenant relation written via WorkspaceCreatorTenantSet event/translator.
- Key files: src/api/iam/domain/aggregates/workspace.py, src/api/iam/application/services/workspace_service.py, src/api/iam/presentation/workspaces/routes.py, src/api/iam/infrastructure/outbox/translator.py, src/api/shared_kernel/authorization/spicedb/schema.zed.
- Run: cd src/api && uv run pytest tests/unit/iam/ -v

### 2026-04-25 | groups.spec.md | PASS | All 10 requirements implemented
- Pattern: Group last-admin guard is in aggregate layer for both remove_member (group.py:160-165) and update_member_role (group.py:198-203) and add_member with current_role (group.py:108-114) — all three code paths covered.
- Action: Verified workspace access inheritance via SpiceDB group#member subject relation (translator.py:604-619, schema.zed:69-75). list_members uses read_relationships (not lookup_subjects) to avoid admin-counting duplicates.
- Context: GroupService.update_group checks duplicate name only when name actually changes (group_service.py:565). Member snapshot captured in GroupDeleted event enables SpiceDB cleanup without external lookups.
- Key files: src/api/iam/domain/aggregates/group.py, src/api/iam/application/services/group_service.py, src/api/iam/presentation/groups/routes.py, src/api/iam/infrastructure/outbox/translator.py, src/api/shared_kernel/authorization/spicedb/schema.zed.
- Run: cd src/api && uv run pytest tests/unit/iam/ -v (175+ tests)

### 2026-04-23 | task-029 Application Lifecycle NFR | PASS | All requirements covered
- Pattern: Graceful shutdown spec requires test proving in-progress batch is NOT interrupted — a `test_stop_clears_running_flag` alone is insufficient; need a timing-based test.
- Action: Verified `test_in_progress_batch_completes_before_shutdown` (test_worker.py:215) injects a slow batch and asserts `processing_completed.is_set()` after `stop()` returns.
- Context: Implementation uses `asyncio.Event` (`_shutdown_event`) + `asyncio.wait_for` in poll loop to interrupt sleep without cancelling task. `stop()` awaits tasks naturally without `task.cancel()`.
- Key files: `src/api/infrastructure/outbox/worker.py`, `src/api/main.py`, `src/api/tests/unit/test_application_lifecycle.py`, `src/api/tests/unit/infrastructure/outbox/test_worker.py`.
- Settings defaults verified in `src/api/infrastructure/settings.py` (IAMSettings): single_tenant_mode=True, default_tenant_name="default", default_workspace_name=None, bootstrap_admin_usernames=[].
