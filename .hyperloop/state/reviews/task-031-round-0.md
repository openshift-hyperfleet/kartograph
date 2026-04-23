---
task_id: task-031
round: 0
role: verifier
verdict: fail
---
## Verification Summary

**Task:** Add full-flow ULID case insensitivity test for tenant context resolution
**Branch:** hyperloop/task-031
**PR:** https://github.com/openshift-hyperfleet/kartograph/pull/362 (CLOSED, 0 commits, 0 files)

## Primary Failure: No Implementation

The branch `hyperloop/task-031` has **zero commits** vs the `alpha` base branch. The PR is
CLOSED with no files changed. The implementation has not been done.

The task requires implementing a **full-flow** test: calling `get_tenant_context()` with a
lowercase ULID header and verifying that all downstream calls (SpiceDB authorization check
and the returned `TenantContext`) use the canonical uppercase ULID.

The existing stub in `src/api/tests/unit/iam/test_tenant_context_dependency.py`
(lines 88–96, `test_normalized_ulid_used_in_spicedb_subject`) has **no assertions and no
test body** — it is an empty placeholder that passes trivially. This is not the
required "full-flow" test.

### What the Implementer Must Add

Fill in `test_normalized_ulid_used_in_spicedb_subject` (or add a separate test) that:

1. Calls `get_tenant_context()` with `x_tenant_id=canonical.lower()` (lowercase ULID)
2. Asserts `mock_authz.check_permission` was called with the **uppercase** normalized ULID
   in the resource argument (not the raw lowercase string)
3. Asserts the returned `TenantContext.tenant_id` equals the canonical uppercase value

Example skeleton:
```python
@pytest.mark.asyncio
async def test_normalized_ulid_used_in_spicedb_subject(
    self,
    valid_tenant_id: TenantId,
    mock_authz: AsyncMock,
    mock_probe: MagicMock,
    mock_tenant_repo: AsyncMock,
) -> None:
    """Full-flow: lowercase header is normalized before SpiceDB and TenantContext."""
    lowercase_header = valid_tenant_id.value.lower()

    result = await get_tenant_context(
        x_tenant_id=lowercase_header,
        user_id="user-123",
        username="alice",
        authz=mock_authz,
        probe=mock_probe,
        single_tenant_mode=False,
        tenant_repository=mock_tenant_repo,
        default_tenant_name="default",
        bootstrap_admin_usernames=[],
    )

    # SpiceDB must receive the canonical uppercase ID
    call_args = mock_authz.check_permission.call_args
    assert valid_tenant_id.value in call_args.kwargs["resource"]

    # Returned context must carry the canonical uppercase ID
    assert result.tenant_id == valid_tenant_id.value
    assert result.tenant_id == lowercase_header.upper()
```

Commit trailers required: `Spec-Ref: specs/shared-kernel/tenant-context.spec.md` and
`Task-Ref: task-031`.

## Checklist Results

| Check | Result | Notes |
|---|---|---|
| 1. Unit Tests | PASS | 2353 passed, 0 failures |
| 2. Linting (ruff) | PASS | All checks passed |
| 3. Formatting (ruff format) | PASS | 476 files already formatted |
| 4. Type Checking (mypy) | PASS | No issues found in 476 source files |
| 5. Architecture Boundary Tests | PASS | 40 passed |
| 6. Integration Tests | N/A | Not run (no infrastructure changes) |
| 7. Code Review | FAIL | No implementation commits; empty test stub |

## Pre-Existing Check Script Failures (not introduced by this task)

The following check scripts fail on this branch because the branch is identical to `alpha`.
These are pre-existing issues, NOT regressions introduced here:

- `check-auth-status-codes.sh`: Integration tests assert 403 in auth files (pre-existing)
- `check-domain-aggregate-mocks.sh`: MagicMock on DataSource in test_knowledge_graph_service.py (pre-existing)
- `check-graceful-shutdown-cancel.sh`: outbox/worker.py uses task.cancel() (pre-existing)
- `check-no-check-script-deletions.sh`: Some scripts missing --exclude-dir=.venv (pre-existing)
- `check-pages-have-tests.sh`: Frontend pages without test coverage (pre-existing)
- `check-partial-error-assertions.sh`: OR-chained assertions in a few test files (pre-existing)

## Action Required

Implement the full-flow ULID case insensitivity test as described above, commit with
conventional commit format, push to the branch, and reopen the PR.