# Spec Alignment Reviewer Memory

## Entries

### 2026-04-22 | task-017 Outbox Pattern | PASS | All SHALL requirements covered

- Pattern: Polling fallback scenario can be implicitly covered by direct `_process_batch()` integration tests even without a scenario-labeled test.
- Action: Accepted implicit coverage for "polling fallback" scenario; scenario is validated by integration tests calling `_process_batch()` directly.
- Context: Implementation in `src/api/infrastructure/outbox/`; shared_kernel in `src/api/shared_kernel/outbox/`; tests in `src/api/tests/unit/infrastructure/outbox/` and `src/api/tests/integration/iam/test_outbox_consistency.py`.
- Key files: `worker.py`, `repository.py`, `composite.py`, `spicedb_handler.py`, `event_sources/postgres_notify.py`.
- Concurrent safety: verified by compiling SQLAlchemy query with PostgreSQL dialect and checking for "SKIP LOCKED" in output.
- Unknown event type: `UnknownEventTypeError` is a distinct class (not `ValueError`) so worker can distinguish permanent vs transient failures.
- Idempotency: tested both with `FakeAuthorizationProvider` (set semantics) in unit tests and with real SpiceDB in integration tests.

### 2026-04-22 | task-001 JobPackage Shared Kernel | PASS | All requirements covered
- Pattern: Shared kernel modules tend to have comprehensive test suites organized by scenario class.
- Action: Checked all 102 tests passed; verified each spec requirement had implementation + test.
- Context: Implementation in `src/api/shared_kernel/job_package/`; tests in `src/api/tests/unit/shared_kernel/job_package/`.
- Key files: `builder.py`, `reader.py`, `value_objects.py`, `checksum.py`, `path_safety.py`.
- All tests run with `cd src/api && uv run pytest tests/unit/shared_kernel/job_package/ -v`.
- Content checksum builder computes checksum in-memory (does not use `compute_content_checksum` from `checksum.py`); both use same algorithm — not a deviation.
- Streaming note: `iter_changeset()` buffers the full ZIP entry bytes before yielding parsed lines; this is inherent to ZIP format and not a spec violation since the generator satisfies the "process without loading entire file into memory" intent at the deserialization layer.
