---
task_id: task-029
round: 0
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review: Application Lifecycle

Reviewed spec: `specs/nfr/application-lifecycle.spec.md`
Branch: `hyperloop/task-029`

---

## Requirement 1: Single-Tenant Mode Bootstrap — COVERED

The system SHALL provision a default tenant and workspace on startup when running in
single-tenant mode.

### Scenario: Default tenant and workspace — COVERED

- **Code:** `src/api/main.py` lines 85–118 — checks `iam_settings.single_tenant_mode`
  before calling `TenantBootstrapService.ensure_default_tenant_with_workspace()`.
  `src/api/iam/application/services/tenant_bootstrap_service.py` — implements idempotent
  creation with race-condition handling via savepoints.
- **Tests:**
  - `tests/unit/test_application_lifecycle.py::TestSingleTenantBootstrap::test_bootstrap_runs_in_single_tenant_mode`
    — verifies `ensure_default_tenant_with_workspace` is called in single-tenant mode.
  - `tests/unit/test_application_lifecycle.py::TestSingleTenantBootstrap::test_workspace_name_defaults_to_tenant_name`
    — verifies workspace_name falls back to tenant_name when `default_workspace_name` is None.
  - `tests/unit/iam/application/test_tenant_bootstrap_service.py::TestEnsureDefaultTenantWithWorkspace::test_creates_tenant_and_workspace_when_neither_exist`
    — verifies creation path.
  - `tests/unit/iam/application/test_tenant_bootstrap_service.py::TestEnsureDefaultTenantWithWorkspace::test_does_nothing_when_tenant_and_workspace_exist`
    — verifies idempotency ("or verified to exist").

### Scenario: Multi-tenant mode — COVERED

- **Code:** `src/api/main.py` line 87 — `if ... iam_settings.single_tenant_mode:` guard
  prevents bootstrap when multi-tenant.
- **Test:**
  - `tests/unit/test_application_lifecycle.py::TestSingleTenantBootstrap::test_bootstrap_skipped_in_multi_tenant_mode`
    — verifies `TenantBootstrapService` is NOT instantiated when `single_tenant_mode=False`.

---

## Requirement 2: Outbox Worker Lifecycle — PARTIAL

The system SHALL start and stop the outbox worker as part of the application lifecycle.

### Scenario: Outbox enabled — COVERED

- **Code:** `src/api/main.py` lines 120–179 — creates `OutboxWorker` with
  `PostgresNotifyEventSource` and calls `worker.start()`.
  `src/api/infrastructure/outbox/worker.py` `start()` method starts both the poll task
  and the event-source task (NOTIFY).
- **Tests:**
  - `tests/unit/test_application_lifecycle.py::TestOutboxWorkerLifecycle::test_outbox_worker_started_when_enabled`
    — verifies `worker.start()` is called.
  - `tests/unit/test_application_lifecycle.py::TestOutboxWorkerLifecycle::test_outbox_worker_not_started_when_disabled`
    — verifies no worker when `enabled=False`.
  - `tests/unit/infrastructure/outbox/test_postgres_notify_event_source.py` — verifies
    NOTIFY event source starts and dispatches callbacks.
  - `tests/integration/iam/test_outbox_consistency.py` (lines 460–540) — verifies
    NOTIFY-based processing works end-to-end.

### Scenario: Graceful shutdown — PARTIAL ← FAIL CONDITION

- **THEN: "the worker stops accepting new events"** — COVERED
  - Code: `OutboxWorker.stop()` sets `_running = False` (line 120), causing the poll
    loop's `while self._running:` check to exit.
  - Test: `tests/unit/infrastructure/outbox/test_worker.py::TestOutboxWorkerLifecycle::test_stop_clears_running_flag`
    — verifies `_running` is False after `stop()`.
  - Test: `tests/unit/test_application_lifecycle.py::TestOutboxWorkerLifecycle::test_outbox_worker_stopped_on_shutdown`
    — verifies `worker.stop()` is called during lifespan teardown.

- **THEN: "in-progress event processing completes before shutdown"** — MISSING
  - **Implementation gap:** `OutboxWorker.stop()` uses `task.cancel()` followed by
    `await task` (worker.py lines 127–132). This cancels the task at its next `await`
    point rather than waiting for the current batch to complete naturally. If a batch is
    mid-flight in `_process_batch()` (e.g., inside `_process_entries()` or before
    `session.commit()`), it is interrupted and the transaction is rolled back. The entries
    remain unprocessed and are retried on next startup, but they do NOT complete before
    shutdown as the spec requires.
  - **Test gap:** No test verifies that an in-progress batch completes before the worker
    stops. The existing tests only check `stop()` is called (mocked worker) or
    `_running` is False (no concurrent processing in flight).
  - **Fix needed:** Either (a) implement graceful draining by allowing the current
    `_process_batch()` call to complete before cancelling (e.g., using a asyncio.Event
    or checking `_running` at the top of the poll loop and awaiting task completion
    rather than cancelling), AND (b) add a test that verifies an in-progress batch
    completes before the worker stops accepting the shutdown signal.

---

## Requirement 3: Database Connection Lifecycle — COVERED

The system SHALL initialize and dispose database connections as part of the application
lifecycle.

### Scenario: Startup — COVERED

- **Code:** `src/api/main.py` line 74 — `init_database_engines(app)` called during
  startup; `src/api/infrastructure/database/dependencies.py` creates write/read engines
  and async sessionmakers.
- **Test:**
  - `tests/unit/test_application_lifecycle.py::TestDatabaseConnectionLifecycle::test_database_engines_initialized_on_startup`
    — verifies `init_database_engines(app)` is called once.

### Scenario: Shutdown — COVERED

- **Code:** `src/api/main.py` line 195 — `await close_database_engines(app)`; lines
  197–205 — closes AGE connection pool and clears LRU cache.
- **Test:**
  - `tests/unit/test_application_lifecycle.py::TestDatabaseConnectionLifecycle::test_database_engines_disposed_on_shutdown`
    — verifies `close_database_engines(app)` is called once on shutdown.

---

## Requirement 4: Default Configuration — COVERED

The system SHALL use sensible defaults for single-tenant deployments.

### Scenario: Default settings — COVERED

- **Code:** `src/api/infrastructure/settings.py` `IAMSettings` class (lines 277–316):
  - `single_tenant_mode: bool = Field(default=True)` ✓
  - `default_tenant_name: str = Field(default="default")` ✓
  - `default_workspace_name: str | None = Field(default=None)` (fallback logic in
    main.py line 111–112) ✓
  - `bootstrap_admin_usernames: list[str] = Field(default_factory=list)` ✓
- **Tests:**
  - `tests/unit/infrastructure/test_settings.py::TestIAMSettingsDefaultConfiguration::test_single_tenant_mode_enabled_by_default` ✓
  - `tests/unit/infrastructure/test_settings.py::TestIAMSettingsDefaultConfiguration::test_default_tenant_name_is_default` ✓
  - `tests/unit/infrastructure/test_settings.py::TestIAMSettingsDefaultConfiguration::test_default_workspace_name_is_none` ✓
  - `tests/unit/infrastructure/test_settings.py::TestIAMSettingsDefaultConfiguration::test_workspace_name_falls_back_to_tenant_name` ✓
  - `tests/unit/infrastructure/test_settings.py::TestIAMSettingsDefaultConfiguration::test_bootstrap_admin_usernames_empty_by_default` ✓

---

## Summary

| Requirement                    | Scenario                       | Status   |
|-------------------------------|-------------------------------|----------|
| Single-Tenant Mode Bootstrap  | Default tenant and workspace  | COVERED  |
| Single-Tenant Mode Bootstrap  | Multi-tenant mode             | COVERED  |
| Outbox Worker Lifecycle       | Outbox enabled                | COVERED  |
| Outbox Worker Lifecycle       | Graceful shutdown             | PARTIAL  |
| Database Connection Lifecycle | Startup                       | COVERED  |
| Database Connection Lifecycle | Shutdown                      | COVERED  |
| Default Configuration         | Default settings              | COVERED  |

**Verdict: FAIL**

The Graceful Shutdown scenario under the SHALL requirement "Outbox Worker Lifecycle" is
PARTIAL. The THEN condition "in-progress event processing completes before shutdown" is
not satisfied:

1. **Implementation:** `OutboxWorker.stop()` calls `task.cancel()` + `await task`, which
   cancels tasks at their next `await` point rather than allowing the current batch to
   finish. Fix by draining the current batch (e.g., set `_running = False`, then `await
   task` without cancellation, relying on the `while self._running:` guard to exit
   naturally after the batch completes).

2. **Test:** No test verifies that a batch in-flight at shutdown time completes before
   the worker stops. Fix by writing a test that starts a worker with a slow handler,
   triggers shutdown, and asserts the in-progress event was fully processed and committed.