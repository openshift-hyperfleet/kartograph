---
id: task-029
title: Gate single-tenant bootstrap on single_tenant_mode setting
spec_ref: specs/nfr/application-lifecycle.spec.md@b46589a2419c1bf08c2dd08c311ee95642139703
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## What

The application lifespan in `src/api/main.py` runs `TenantBootstrapService` whenever a
database session is available — regardless of the `single_tenant_mode` setting. The spec
requires that in multi-tenant mode, **no default tenant or workspace is created**.

## Spec Scenarios Addressed

**Requirement: Single-Tenant Mode Bootstrap**

- Scenario: Default tenant and workspace — GIVEN single-tenant mode is enabled, the
  bootstrap runs (currently: always runs — PARTIAL)
- Scenario: Multi-tenant mode — GIVEN single-tenant mode is disabled, no default
  tenant or workspace is created (currently: **not enforced** — this is the gap)

## Where the Gap Is

`src/api/main.py`, around line 80, the bootstrap block:

```python
# Startup: ensure default tenant and root workspace exist (single-tenant mode)
if hasattr(app.state, "write_sessionmaker"):   # <-- missing single_tenant_mode check
    ...
    await bootstrap_service.ensure_default_tenant_with_workspace(...)
```

`iam_settings` is already read inside the block but its `single_tenant_mode` flag is
never used to gate the entire block.

## Work Required

1. **Write tests first** (TDD). In `src/api/tests/unit/iam/application/test_tenant_bootstrap_service.py`
   or a lifespan-level test, add:
   - `test_bootstrap_skipped_in_multi_tenant_mode`: configure `single_tenant_mode=False`,
     simulate lifespan startup, assert `TenantBootstrapService.ensure_default_tenant_with_workspace`
     is never called.
   - Verify the existing `test_bootstrap_runs_in_single_tenant_mode` (or equivalent)
     still passes.

2. **Fix `src/api/main.py`** — read `iam_settings` before the guard and add the
   `single_tenant_mode` check:

   ```python
   iam_settings = get_iam_settings()

   # Startup: ensure default tenant and root workspace exist (single-tenant mode only)
   if iam_settings.single_tenant_mode and hasattr(app.state, "write_sessionmaker"):
       ...
       await bootstrap_service.ensure_default_tenant_with_workspace(
           tenant_name=iam_settings.default_tenant_name,
           workspace_name=workspace_name,
       )
   ```

   Note: `get_iam_settings()` is already imported and called inside the block; move it
   outside so it can gate the block.

## Acceptance Criteria

- When `single_tenant_mode=False`, `TenantBootstrapService` is never invoked during startup
- When `single_tenant_mode=True`, bootstrap runs as before (existing behavior preserved)
- Unit test asserts the skip behavior in multi-tenant mode
- All existing bootstrap tests continue to pass
