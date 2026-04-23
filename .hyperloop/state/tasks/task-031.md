---
id: task-031
title: Add full-flow ULID case insensitivity test for tenant context resolution
spec_ref: specs/shared-kernel/tenant-context.spec.md@ded09d09b3de73d6ed9527214fcd081069a55630
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## What

The tenant context spec requires that a lowercase `X-Tenant-ID` ULID is normalized to
uppercase and the request proceeds normally. The unit test that was supposed to exercise
this full flow — `test_normalized_ulid_used_in_spicedb_subject` in
`src/api/tests/unit/iam/test_tenant_context_dependency.py` — is an **empty stub with no
assertions**. The comment inside it incorrectly claims the scenario is covered by
`test_returns_tenant_context_with_valid_ulid_header`, but that test uses an already-uppercase
ULID and never exercises the lowercase path.

The normalization of `_validate_ulid` is tested in isolation
(`test_normalizes_lowercase_ulid_to_uppercase`), but the full composition — a lowercase
ULID arriving in `get_tenant_context`, being normalized, and the normalized value being
used for the SpiceDB permission check — is untested.

## Spec Scenario Addressed

**Requirement: Multi-Tenant Header Resolution**

> **Scenario: ULID case insensitivity**
> - GIVEN an `X-Tenant-ID` header with a lowercase ULID
> - WHEN the tenant context is resolved
> - THEN the ULID is normalized to uppercase
> - AND the request proceeds normally

## Where the Gap Is

File: `src/api/tests/unit/iam/test_tenant_context_dependency.py`
Class: `TestValidateUlidNormalization`
Stub: `test_normalized_ulid_used_in_spicedb_subject` — has no assertions, passes vacuously.

## Work Required

1. Fill in or replace `test_normalized_ulid_used_in_spicedb_subject` with a real
   async test that calls `get_tenant_context` with a **lowercase** ULID as `x_tenant_id`:

   ```python
   @pytest.mark.asyncio
   async def test_normalized_ulid_used_in_spicedb_subject(
       self,
       valid_tenant_id: TenantId,
       mock_authz: AsyncMock,
       mock_probe: MagicMock,
       mock_tenant_repo: AsyncMock,
   ) -> None:
       """SpiceDB check must use the normalized (uppercase) tenant ID, not the raw
       lowercase value from the header."""
       lowercase_ulid = valid_tenant_id.value.lower()

       result = await get_tenant_context(
           x_tenant_id=lowercase_ulid,
           user_id="user-123",
           username="alice",
           authz=mock_authz,
           probe=mock_probe,
           single_tenant_mode=False,
           tenant_repository=mock_tenant_repo,
           default_tenant_name="default",
           bootstrap_admin_usernames=[],
       )

       # Request proceeds — TenantContext is returned
       assert isinstance(result, TenantContext)
       assert result.tenant_id == valid_tenant_id.value   # normalized to uppercase
       assert result.source == "header"

       # SpiceDB was called with the canonical (uppercase) tenant ID
       mock_authz.check_permission.assert_awaited_once_with(
           resource=f"tenant:{valid_tenant_id.value}",
           permission="view",
           subject="user:user-123",
       )
   ```

2. The existing `test_normalizes_lowercase_ulid_to_uppercase` (isolation test of
   `_validate_ulid`) is correct and should be kept as-is.

3. No production code changes are expected — the normalization already works
   (proven by the isolation test). This task only fills in the missing contract test.

## Acceptance Criteria

- `test_normalized_ulid_used_in_spicedb_subject` has real assertions (not empty body)
- Test passes a lowercase ULID to `get_tenant_context` and asserts:
  - The returned `TenantContext.tenant_id` is the uppercase canonical form
  - `result.source == "header"`
  - SpiceDB `check_permission` was called with the normalized (uppercase) tenant ID
- All existing tests in `test_tenant_context_dependency.py` continue to pass
- `make test-unit` passes with no failures
