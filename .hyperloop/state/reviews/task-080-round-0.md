---
task_id: task-080
round: 0
role: verifier
verdict: fail
---
## Verification Summary

### Task Scope
Task-080 adds an `AlertDialog` shadcn/vue component set (backed by reka-ui) and migrates three pages (api-keys, groups, workspaces) from plain `Dialog` to `AlertDialog` for all destructive confirmation flows. Two commits with correct `Spec-Ref` and `Task-Ref` trailers.

---

## Check Results

### PASS — Frontend Tests (1329 tests, 30 files)
All 1329 frontend vitest tests pass. The new `alert-dialog.test.ts` (41 tests) passes cleanly, covering file existence, index exports, reka-ui primitive usage, Tailwind design-language classes, and migration of api-keys/groups/workspaces pages.

### PASS — Frontend Type Check (vue-tsc)
Zero type errors reported.

### PASS — Frontend Lockfile Frozen
`pnpm-lock.yaml` is in sync with `package.json`.

### PASS — Backend Unit Tests (2707 passed)
Zero failures.

### PASS — Architecture Boundary Tests (40 passed)
All pytest-archon rules hold.

### PASS — Backend Ruff Linting
Zero violations.

### PASS — Backend mypy
Zero type errors.

### PASS — Commit Trailers
Both commits carry `Spec-Ref` and `Task-Ref: task-080`.

### PASS — All other infrastructure checks
Branch rebases cleanly on alpha, no state-file commits, no foreign-task commits, no coming-soon stubs, no direct logger usage, pages have tests, selector forwarding, watch-handler reload tests, route-handler mock coverage (Section 1 blocking).

---

## FAIL — check-no-duplicate-vue-imports.sh (NEW defect introduced by this task)

Eight of the ten new alert-dialog component files contain two separate import blocks from `"reka-ui"` — one `import type { ... }` and one `import { ... }`. The check uses `uniq -d` on all `from "..."` occurrences; both forms match `from "reka-ui"`, so each file is flagged.

**Failing files:**
- `src/dev-ui/app/components/ui/alert-dialog/AlertDialog.vue`
- `src/dev-ui/app/components/ui/alert-dialog/AlertDialogAction.vue`
- `src/dev-ui/app/components/ui/alert-dialog/AlertDialogCancel.vue`
- `src/dev-ui/app/components/ui/alert-dialog/AlertDialogContent.vue`
- `src/dev-ui/app/components/ui/alert-dialog/AlertDialogDescription.vue`
- `src/dev-ui/app/components/ui/alert-dialog/AlertDialogOverlay.vue`
- `src/dev-ui/app/components/ui/alert-dialog/AlertDialogTitle.vue`
- `src/dev-ui/app/components/ui/alert-dialog/AlertDialogTrigger.vue`

**Required fix (example for AlertDialogAction.vue):**

Current (broken):
```ts
import type { AlertDialogActionProps } from "reka-ui"
import { AlertDialogAction } from "reka-ui"
```

Fixed (merged with inline `type` modifier):
```ts
import { type AlertDialogActionProps, AlertDialogAction } from "reka-ui"
```

Apply the same merge to all eight files. This is the pattern established by shadcn/vue and used elsewhere in the codebase.

---

## NOTE — Pre-existing backend failures (NOT introduced by this task)

Two backend checks also failed in `check-run-backend-suite.sh`, but these failures pre-exist on `alpha` and are unrelated to this task's diff:

- **check-no-repo-port-mocks.sh**: `test_tenant_service.py` (line 1771 `mock_probe = MagicMock()`) and `test_data_source_service.py` (AsyncMock fixtures) exist unchanged on `alpha`. This task touched zero Python files.
- **check-cascade-delete-rollback-test.sh**: Missing service-level rollback integration tests for `group`, `tenant`, and `data_source` services — again pre-existing on `alpha`.

These must be tracked but are **not attributable to task-080**.

---

## Actionable Items for Implementer

1. **[Blocking]** In each of the 8 alert-dialog `.vue` files listed above, merge the two `from "reka-ui"` import lines into a single statement using TypeScript's inline `type` modifier:
   ```ts
   // Before (two lines):
   import type { AlertDialogFooProps } from "reka-ui"
   import { AlertDialogFoo } from "reka-ui"

   // After (one line):
   import { type AlertDialogFooProps, AlertDialogFoo } from "reka-ui"
   ```
2. Re-run `bash .hyperloop/checks/check-no-duplicate-vue-imports.sh` to confirm exit 0.
3. Re-run `bash .hyperloop/checks/check-frontend-type-check.sh` to confirm vue-tsc still passes after the merge.
4. Commit the fix and resubmit.