---
task_id: audit-specs/iam/workspaces.spec.md@b46589a2419c1bf08c2dd08c311ee95642139703
round: 0
role: auditor
verdict: fail
---
## Alignment Auditor Verdict — specs/iam/workspaces.spec.md

Spec ref: specs/iam/workspaces.spec.md@b46589a2419c1bf08c2dd08c311ee95642139703
Date: 2026-04-28

---

## Summary

The workspace implementation is largely faithful to the spec. Root workspace
creation, child creation, name validation, retrieval, listing, rename, deletion,
member management, member listing, and the three-tier role hierarchy are all
present and well-tested.

However, two gaps constitute a meaningful divergence from the spec:

1. **SpiceDB schema grants `view` to ALL tenant members on every workspace**,
   bypassing the spec's per-workspace access control model.
2. **`delete_workspace` returns HTTP 403 on unauthorized access** rather than
   404, violating the "no distinction between unauthorized and missing"
   principle the spec establishes.

---

## GAP 1 — SpiceDB schema grants `view` to ALL tenant members (SPEC VIOLATION)

**File:** `src/api/shared_kernel/authorization/spicedb/schema.zed`

**Line:** ~83–84
```
permission view = admin + editor + member + tenant->view
```

**Spec requirement:**
- Req. 4: "Only users with `view` permission see it" (workspace retrieval)
- Req. 5: "Only workspaces the requesting user has `view` permission on"
- Req. 10: Three-tier hierarchy — `member` role grants `view` only

**What the code does:** The `tenant->view` term causes every member of the
tenant to automatically have `view` permission on every workspace in that
tenant. Explicit workspace membership (admin/editor/member roles) is therefore
irrelevant for the basic visibility gate — all tenant members already pass.

**Why this matters:** The spec describes per-workspace access control where
users must be explicitly granted a role to see a workspace. The current schema
makes workspace-level membership redundant for viewing: a tenant member who
has never been added to workspace X can still list and retrieve it. The
three-tier role hierarchy's `member` entry is effectively a no-op for visibility
since all tenant members already inherit `view`. This directly contradicts
Req. 5's "filtered listing" scenario: "workspace C is excluded" (for a user
without `view` on C) cannot happen if all tenant members inherit view on all
workspaces.

---

## GAP 2 — `delete_workspace` returns 403 on unauthorized access, not 404 (SPEC VIOLATION)

**File:** `src/api/iam/presentation/workspaces/routes.py`

**Lines:** ~268–272
```python
except UnauthorizedError:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to perform this action",
    )
```

**Spec requirement:** The spec's consistent "no distinction between unauthorized
and missing" principle is explicitly stated for workspace retrieval (Req. 4) and
child creation (Req. 2). The same privacy-preserving philosophy should apply to
deletion.

**What the code does:** When a user attempts to delete a workspace they lack
`manage` permission on (or a workspace belonging to a different tenant), the
route returns **HTTP 403 Forbidden**, distinguishing the "no permission" case
from the "not found" case (HTTP 404). A caller can use this to infer that the
workspace ID exists in a different tenant.

**Contrast:** The `create_workspace` route correctly converts `UnauthorizedError`
to 404. The `get_workspace` route returns 404 for both unauthorized and missing
(via the None-check pattern). Only `delete_workspace` breaks this pattern.

**Test reference:** `tests/unit/iam/presentation/test_workspaces_routes.py`
contains a test that explicitly expects 403, confirming this is intentional but
misaligned with the spec's information-hiding philosophy.

---

## Minor Observations (not verdict-blocking)

### OBSERVATION A — Root workspace creator gets workspace admin (undocumented)

**File:** `src/api/iam/application/services/tenant_service.py`, lines ~102–114

The spec (Req. 1) says only the `creator_tenant` relationship is established on
the root workspace (granting `create_child` to all tenant members). The code
additionally calls `workspace.add_member(creator_id, ADMIN)`, granting the
tenant creator workspace admin on the root workspace. This is more generous than
the spec describes but not harmful.

### OBSERVATION B — Adding a member who already has the same role returns 400

**File:** `src/api/iam/domain/aggregates/workspace.py`, lines ~262–265

`Workspace.add_member()` raises `ValueError` if the member already holds the
exact role being added. The route converts this to HTTP 400. The spec does not
document this edge case, so the behavior is technically unspecified rather than
incorrect.

### OBSERVATION C — Root workspace auto-creation: two code paths are inconsistent

`TenantService.create_tenant()` creates root workspace AND adds creator as admin.
`TenantBootstrapService._ensure_root_workspace()` creates root workspace without
adding any admin member. This inconsistency (Observation A) means idempotent
bootstrap of an existing tenant without a root workspace produces a root workspace
with no direct admin member.

---

## Confirmed Implementations

| Spec Requirement | Status |
|---|---|
| Root workspace auto-created at tenant creation | ✓ PASS |
| `creator_tenant` relationship established | ✓ PASS |
| Root workspace cannot be deleted (→ 409) | ✓ PASS |
| Child creation requires `create_child` permission | ✓ PASS |
| Unauthorized creation → 404 (no distinction) | ✓ PASS |
| Duplicate workspace name → 409 conflict | ✓ PASS |
| Creator granted admin role on new workspace | ✓ PASS |
| Name validation: 1–512 chars | ✓ PASS |
| Retrieval: unauthorized or missing → 404 | ✓ PASS |
| Listing filtered by `view` permission | ✓ PASS (but see GAP 1) |
| Rename requires `manage` | ✓ PASS |
| Rename duplicate name → 409 | ✓ PASS |
| Delete: non-root leaf, `manage` required | ✓ PASS |
| Delete: has children → 409 | ✓ PASS |
| Delete: member snapshot captured for auth cleanup | ✓ PASS |
| Delete: unauthorized access → **FAIL** (returns 403) | ✗ GAP 2 |
| Member add/remove/update requires `manage` | ✓ PASS |
| Add group member (group-type grant) | ✓ PASS |
| Change role: revoke old, grant new | ✓ PASS |
| Last admin cannot be removed/demoted → 409 | ✓ PASS |
| Member listing requires `view` | ✓ PASS |
| Group entries shown as group-type (not expanded) | ✓ PASS |
| admin → manage + edit + view | ✓ PASS |
| editor → edit + view (no manage) | ✓ PASS |
| member → view only (no edit or manage) | ✓ PASS (schema correct, but GAP 1 makes it moot) |