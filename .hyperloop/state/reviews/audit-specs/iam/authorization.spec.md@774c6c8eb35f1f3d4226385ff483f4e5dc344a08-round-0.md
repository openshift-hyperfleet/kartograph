---
task_id: audit-specs/iam/authorization.spec.md@774c6c8eb35f1f3d4226385ff483f4e5dc344a08
round: 0
role: auditor
verdict: fail
---
## Alignment Audit — specs/iam/authorization.spec.md

### VERDICT: FAIL

One requirement is **not implemented** as the spec mandates. All other
requirements pass.

---

## GAP-001 — Information Hiding on Authorization Failure (mutations)

**Requirement:** "GIVEN a user without permission to view a resource / WHEN the
user requests the resource / THEN a not-found response is returned (not
forbidden) / AND the response is indistinguishable from a genuinely missing
resource."

**Status: FAIL — mutation routes return 403 instead of 404.**

The GET endpoints correctly return 404 for both missing and unauthorized
resources. However, every mutating operation on groups (and likely other
resource types) returns **403 Forbidden** when the user lacks permission,
directly violating the spec's requirement for indistinguishable not-found
responses.

### Evidence

**Route implementation:**

- `src/api/iam/presentation/groups/routes.py` lines 262-264
  `delete_group` catches `UnauthorizedError` → raises `HTTP 403`.
  When a random/nonexistent UUID is given, SpiceDB finds no MANAGE relationship
  and the service raises `UnauthorizedError`. The caller receives 403, not 404.

- `src/api/iam/presentation/groups/routes.py` lines 189-193
  `update_group` (PATCH) returns 403 on `UnauthorizedError`.

- `src/api/iam/presentation/groups/routes.py` lines 328-332
  `add_group_member` (POST /{id}/members) returns 403 on `UnauthorizedError`.

- `src/api/iam/presentation/groups/routes.py` lines 397-400
  `list_group_members` (GET /{id}/members) returns 403 on `UnauthorizedError`.

- `src/api/iam/presentation/groups/routes.py` lines 464-467
  `update_group_member_role` returns 403 on `UnauthorizedError`.

- `src/api/iam/presentation/groups/routes.py` lines 535-538
  `remove_group_member` returns 403 on `UnauthorizedError`.

**Test that encodes the wrong behaviour:**

- `src/api/tests/integration/iam/test_api.py` lines 222-232
  `test_returns_403_for_nonexistent_group` explicitly asserts DELETE on a
  nonexistent UUID returns 403.  The comment reads "Returns 403 (not 404) to
  avoid leaking group existence information" — the logic is inverted: a 403
  reveals that an authorization check was performed and denied, whereas 404 is
  the response the spec requires for both missing and unauthorized resources.

### What must change

All mutation endpoints (DELETE, PATCH, POST sub-resources) must catch
`UnauthorizedError` and raise `HTTP 404` rather than `HTTP 403`, consistent with
how the GET endpoints already behave. The test at line 222 must be updated to
expect 404.

---

## Passing Requirements

All other requirements in the spec are faithfully implemented.

### Tenant Permissions
**PASS.**
`schema.zed` lines 170–180:
- `view = admin + member` ✓
- `create_api_key = admin + member` ✓
- `manage = admin` (member excluded) ✓
- `administrate = admin` (member excluded) ✓

### Workspace Permissions
**PASS.**
`schema.zed` lines 83–98:
- `view = admin + editor + member + tenant->view` ✓ (tenant members see all workspaces)
- `edit = admin + editor` ✓
- `manage = admin` ✓
- `create_child = admin + editor + creator_tenant->view` ✓ (member excluded)

### Root Workspace Create-Child Access
**PASS.**
`schema.zed` lines 61–66 defines `creator_tenant` relation; line 98 includes
`creator_tenant->view` in `create_child`. The outbox translator writes this
relationship only for root workspaces, ensuring child workspaces restrict
creation to admin/editor only.

### Group-to-Workspace Permission Inheritance
**PASS.**
`schema.zed` lines 69–75 accept `group#member` as subjects for workspace
admin/editor/member relations. The `member` permission on group (line 37)
expands to `admin + member_relation`, so group admins inherit workspace
permissions. Removing a user from a group removes the subject relation,
revoking inherited access via SpiceDB.

### Knowledge Graph Permissions
**PASS.**
`schema.zed` lines 124–130:
- `view = admin + editor + viewer + workspace->view` ✓
- `edit = admin + editor + workspace->edit` ✓
- `manage = admin + workspace->manage` ✓
Direct admin → manage + edit + view; workspace edit → KG edit (and view via
the workspace->view chain).

### Data Source Permissions
**PASS.**
`schema.zed` lines 146–152 derive all permissions from the parent KG:
`view = knowledge_graph->view`, `edit = knowledge_graph->edit`,
`manage = knowledge_graph->manage`.

### API Key Permissions
**PASS.**
`schema.zed` lines 196–199:
- `view = owner + tenant->administrate` ✓
- `revoke = owner + tenant->administrate` ✓
Tenant `administrate = admin` (line 180) gives admins view/revoke on all keys.

### Secure Enclave — Per-Entity Graph Authorization
**PASS.**
`src/api/graph/application/services/graph_secure_enclave.py`:
- Authorized entities returned in full (lines 152–153, 168–169).
- Unauthorized nodes → `RedactedNodeRecord(id=node.id)` only (lines 150, 155).
- Unauthorized edges → `RedactedEdgeRecord(id, start_id, end_id)` only
  (lines 162–165, 171–174).
- Graph topology preserved — no entity is removed from the result set
  (lines 113–133).
- `_extract_kg_id` (lines 218–220) returns `None` for absent, null, non-string,
  or empty `knowledge_graph_id`; `_authorize_node`/`_authorize_edge` deny
  immediately on `None` (lines 148–150, 160–162).
- Permission errors in `_check_kg_view` fail safe to deny (lines 198–200).

### Single-Role Enforcement
**PASS.**
Role-assignment logic across tenant, workspace, and group services retrieves
the current role and removes it before writing the new role. Integration tests
in `tests/integration/iam/test_single_role_enforcement.py` cover all three
resource types and verify the old role is absent after the update.

### Information Hiding — GET operations only
**PASS (partial).**
GET routes return `None` from the service when authorization is denied, and the
route converts `None` to 404 (e.g., `groups/routes.py` lines 136–140).
`test_returns_404_for_nonexistent_group` confirms GET behaviour is correct.
(The failure is confined to mutation verbs — see GAP-001.)

### Group Permissions
**PASS.**
`schema.zed` lines 40–43:
- `view = admin + member_relation + tenant->view` ✓ (tenant members see all groups)
- `manage = admin` ✓ (member excluded)