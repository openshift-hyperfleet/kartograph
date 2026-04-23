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

### 2026-04-23 | task-029 Application Lifecycle NFR | PASS | All requirements covered
- Pattern: Graceful shutdown spec requires test proving in-progress batch is NOT interrupted — a `test_stop_clears_running_flag` alone is insufficient; need a timing-based test.
- Action: Verified `test_in_progress_batch_completes_before_shutdown` (test_worker.py:215) injects a slow batch and asserts `processing_completed.is_set()` after `stop()` returns.
- Context: Implementation uses `asyncio.Event` (`_shutdown_event`) + `asyncio.wait_for` in poll loop to interrupt sleep without cancelling task. `stop()` awaits tasks naturally without `task.cancel()`.
- Key files: `src/api/infrastructure/outbox/worker.py`, `src/api/main.py`, `src/api/tests/unit/test_application_lifecycle.py`, `src/api/tests/unit/infrastructure/outbox/test_worker.py`.
- Settings defaults verified in `src/api/infrastructure/settings.py` (IAMSettings): single_tenant_mode=True, default_tenant_name="default", default_workspace_name=None, bootstrap_admin_usernames=[].
