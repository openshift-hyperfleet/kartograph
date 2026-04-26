# Intake Review: Seventh Run — 2026-04-25

## Specs Reviewed

| Spec | Status | Decision | Reason |
|------|--------|----------|--------|
| `specs/iam/tenants.spec.md` | modified | No new task | task-037 covers both new AND-clauses (transaction leak + atomicity). Already not-started. |
| `specs/index.spec.md` | new | No task | Pure table-of-contents; no requirements or scenarios. |
| `specs/nfr/api-conventions.spec.md` | new | No task | Explicitly tagged NFR; guideline not deliverable. |
| `specs/nfr/architecture.spec.md` | new | No task | Explicitly tagged NFR; guideline not deliverable. |
| `specs/nfr/observability.spec.md` | new | No task | Explicitly tagged NFR; guideline not deliverable. |
| `specs/nfr/testing.spec.md` | new | No task | Explicitly tagged NFR; guideline not deliverable. |
| `specs/shared-kernel/tenant-context.spec.md` | modified | No task | Content hash `ded09d09b3de73d6ed9527214fcd081069a55630` unchanged from task-031. All 13 scenarios verified implemented. |

## Verification

### `specs/iam/tenants.spec.md`

The diff adds two AND-clauses to the **Scenario: Tenant graph provisioning**:

> - AND the database connection MUST be properly committed or rolled back on all code
>   paths (including the no-op/exists path) to avoid leaking open transactions back to
>   the connection pool
> - AND the existence check and graph creation MUST be performed atomically (e.g. via
>   `CREATE GRAPH IF NOT EXISTS` or an advisory lock) to prevent race conditions under
>   concurrent duplicate event deliveries

**task-037** (not-started) targets `src/api/graph/infrastructure/tenant_graph_handler.py`
and specifies TDD tests for both the transaction-leak bug and the TOCTOU race condition.
These requirements map directly to task-037's bug descriptions and fix strategy.

### NFR Specs

All four (`api-conventions`, `architecture`, `observability`, `testing`) carry the
`NFR:` tag in their opening line. Per guidelines: "NFR specs are NOT implementation
tasks. They are guidelines. Do not create tasks for them."

### `specs/index.spec.md`

Navigational index with no Requirements, Scenarios, or behavioral contracts.

### `specs/shared-kernel/tenant-context.spec.md`

Content verified byte-for-byte identical to blob `ded09d09b3de73d6ed9527214fcd081069a55630`
(the blob hash in task-031's `spec_ref`). Full scenario coverage:

**Multi-Tenant Header Resolution (5/5 scenarios):**
- Valid header → `get_tenant_context`, checks authz, returns `TenantContext` ✅
- Missing header → HTTP 400 ✅
- Invalid ULID format → HTTP 400 ✅
- ULID case insensitivity → `_validate_ulid` normalizes to uppercase ✅ (task-031)
- Unauthorized tenant access → HTTP 403 ✅

**Single-Tenant Auto-Selection (4/4 scenarios):**
- Auto-select default tenant → `_resolve_default_tenant` ✅
- Auto-provision member access → `add_member(role=TenantRole.MEMBER)` ✅
- Bootstrap admin auto-provision → `username in bootstrap_admin_usernames` → ADMIN ✅
- Default tenant missing → HTTP 500 ✅

**MCP Authentication (4/4 scenarios):**
- API key auth → `MCPApiKeyAuthMiddleware._authenticate_api_key` → sets MCPAuthContext ✅
- Bearer token fallback → `MCPApiKeyAuthMiddleware._authenticate_bearer` ✅
- Authentication failure → HTTP 401 ✅
- Service unavailability → HTTP 503 (exception in validator) ✅

All scenarios tested in `test_tenant_context_dependency.py` and
`test_mcp_auth_middleware.py`.

## Conclusion

No new task files created. **task-037** remains the sole open deliverable from this
spec batch. No dependency cycles introduced (task-037 has no deps).
