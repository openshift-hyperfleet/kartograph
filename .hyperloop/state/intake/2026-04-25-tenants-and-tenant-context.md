# Intake Review: Tenants (modified) + Tenant Context (modified) + NFR/Index
## Date: 2026-04-25

## Specs Reviewed

| Spec | Status | Decision | Reason |
|------|--------|----------|--------|
| `specs/iam/tenants.spec.md` | modified | No new task | task-037 (commit 2ab8b665) already captures the two new bullet points added to the Tenant Graph Provisioning scenario |
| `specs/index.spec.md` | new | No task | Pure table-of-contents; no requirements or scenarios. Previously confirmed in 2026-04-23-index-and-nfr-specs.md |
| `specs/nfr/api-conventions.spec.md` | new | No task | Explicitly tagged NFR; guideline for implementers, not a deliverable |
| `specs/nfr/architecture.spec.md` | new | No task | Explicitly tagged NFR; enforced via pytest-archon in bounded-context tasks |
| `specs/nfr/observability.spec.md` | new | No task | Explicitly tagged NFR; probe patterns applied per-context |
| `specs/nfr/testing.spec.md` | new | No task | Explicitly tagged NFR; testing philosophy applied per-context |
| `specs/shared-kernel/tenant-context.spec.md` | modified | No task | Zero content change vs blob ded09d09b3de73d6ed9527214fcd081069a55630; all 13 scenarios verified implemented |

---

## Detailed Findings

### `specs/iam/tenants.spec.md`

The diff adds two AND-clauses to **Scenario: Tenant graph provisioning**:

> - AND the database connection MUST be properly committed or rolled back on all code paths
>   (including the no-op/exists path) to avoid leaking open transactions back to the connection pool
> - AND the existence check and graph creation MUST be performed atomically (e.g. via
>   `CREATE GRAPH IF NOT EXISTS` or an advisory lock) to prevent race conditions under concurrent
>   duplicate event deliveries

`task-037` was created in the previous intake run (commit `2ab8b665`) and captures both
requirements in detail, including the specific code location in
`src/api/graph/infrastructure/tenant_graph_handler.py` and the TDD approach to fix them.

**Status**: Covered by task-037 (not-started). No new task needed.

---

### `specs/shared-kernel/tenant-context.spec.md`

The `spec_ref` in task-031 references blob `ded09d09b3de73d6ed9527214fcd081069a55630`.
Running `diff` between that blob and the current HEAD version produces no output — the files
are identical in content.

Full scenario-by-scenario verification was performed:

#### Requirement: Multi-Tenant Header Resolution (5 scenarios)

| Scenario | Implementation | Test |
|----------|----------------|------|
| Valid header | `get_tenant_context()` — Case 3 path | `test_returns_tenant_context_with_valid_ulid_header` |
| Missing header (multi-tenant) | returns 400 | `test_returns_400_when_header_missing_in_multi_tenant_mode` |
| Invalid ULID format | returns 400 | `TestGetTenantContextInvalidULID` (4 tests) |
| ULID case insensitivity | `_validate_ulid()` normalizes to uppercase | `test_normalizes_lowercase_ulid_to_uppercase` + full-flow test (task-031) |
| Unauthorized tenant access | returns 403 | `test_returns_403_when_user_not_member_of_tenant` |

#### Requirement: Single-Tenant Auto-Selection (4 scenarios)

| Scenario | Implementation | Test |
|----------|----------------|------|
| Auto-select default tenant | `_resolve_default_tenant()` | `test_auto_selects_default_tenant_when_user_already_member` |
| Auto-provision member access | `tenant.add_member(role=MEMBER)` + `save()` + `commit()` | `test_auto_adds_user_as_member_when_not_in_tenant` |
| Bootstrap admin auto-provision | `role=ADMIN` when `username in bootstrap_admin_usernames` | `test_auto_adds_user_as_admin_when_in_bootstrap_list` |
| Default tenant missing | returns 500 | `test_raises_500_when_default_tenant_not_found` |

#### Requirement: MCP Authentication (4 scenarios)

| Scenario | Implementation | Test |
|----------|----------------|------|
| API key authentication | `MCPApiKeyAuthMiddleware._authenticate_api_key()` | `test_sets_auth_context_on_valid_key` |
| Bearer token fallback | `MCPApiKeyAuthMiddleware._authenticate_bearer()` | `test_falls_back_to_bearer_when_api_key_missing` |
| Authentication failure | returns 401 | `test_returns_401_when_header_missing`, `test_returns_401_when_key_invalid` |
| Service unavailability | returns 503 | `test_returns_503_when_validator_raises` |

**All 13 scenarios: fully implemented and tested. No gaps.**

---

## Conclusion

No new task files were created in this intake run.

- `task-037` (created 2026-04-25 in commit 2ab8b665) remains the only open item from the
  modified specs above.
- NFR specs and the index are confirmed as guidelines — no tasks per project policy.
- The tenant-context spec is 100% covered across all requirements and scenarios.
