---
task_id: task-041
round: 2
role: verifier
verdict: fail
---
## Summary

task-041 implements two UI bug fixes: (1) correcting the knowledge-graph creation API call to use the workspace-scoped endpoint, and (2) fixing loadDataSources to correctly handle direct-array API responses. The backend tests, ruff, mypy, and architecture boundary tests all pass. However, the branch has a design-language violation in the changed code.

---

## Check Results

| Check | Result | Notes |
|-------|--------|-------|
| Unit tests (backend) | PASS | 2684 passed, 0 failures |
| Unit tests (frontend) | PASS | 459 passed across 16 test files |
| Linting (ruff) | PASS | 0 violations |
| Formatting (ruff format) | PASS | Clean |
| Type checking (mypy) | PASS | 0 errors in 542 source files |
| Architecture boundary tests | PASS | 40 tests pass |
| Branch rebases on alpha | PASS | 0 commits behind alpha; dry-run rebase clean |
| All commits have Task-Ref | PASS | Both commits carry `Task-Ref: task-041` and `Spec-Ref` |
| No foreign-task commits | PASS | Clean |
| No state-file commits | PASS | Clean |
| No source regressions | PASS | No unspecified regressions vs alpha |
| No test regressions | PASS | No deleted or truncated test files |
| No placeholder comments | PASS | Clean |
| No coming-soon stubs | PASS | Clean |
| Pages have test coverage | PASS | All 13 pages covered |
| check-run-backend-suite (full) | FAIL (pre-existing) | See note below |
| Design language – component library | FAIL | See Finding 1 |
| Dead imports | FAIL | See Finding 2 |

### Pre-existing backend check failures (NOT introduced by this branch)

`check-run-backend-suite.sh` fails because two checks were already failing on `alpha` before this branch was cut:

- `check-no-repo-port-mocks.sh` — `test_tenant_service.py` and `test_data_source_service.py` use `AsyncMock`/`MagicMock` for repository ports and probe protocols instead of in-memory fakes.
- `check-cascade-delete-rollback-test.sh` — `GroupService` and `TenantService` are missing service-level rollback integration tests.

These failures exist identically on `alpha` and are unrelated to this task. They should be tracked as separate tasks and do not block this PR on their own merits.

---

## Actionable Findings

### Finding 1 — FAIL: Design language violation (native `<select>` replaces Reka UI `<Select>`)

**File:** `src/dev-ui/app/pages/knowledge-graphs/index.vue` — template, workspace selector (approx. line 308)

**Spec requirement (Design Language → Component library):**
> GIVEN any UI component
> THEN it uses shadcn/vue (Reka UI) primitives with Tailwind CSS

The commit replaced the shadcn/vue `<Select>` component with a raw HTML `<select>` element. Although Tailwind classes are applied to make it look similar, this bypasses the Reka UI component library required by the spec. The original `<Select>` primitive was already present; the conditional loading/empty states can be built around it (e.g. using a `v-if` on the `<SelectContent>`, or rendering a disabled `<SelectTrigger>` with the appropriate placeholder text while loading).

**Fix:** Restore the `<Select>` / `<SelectTrigger>` / `<SelectContent>` / `<SelectItem>` structure. Handle the loading state by passing a dynamic placeholder to `<SelectValue>` and disabling the trigger; handle the "no workspaces" case with a `<p>` outside the `<Select>`.

---

### Finding 2 — FAIL: Dead imports left in place

**File:** `src/dev-ui/app/pages/knowledge-graphs/index.vue`, lines 29–34

```ts
import {
  Select,          // ← unused
  SelectContent,   // ← unused
  SelectItem,      // ← unused
  SelectTrigger,   // ← unused
  SelectValue,     // ← unused
} from '@/components/ui/select'
```

These five named imports are no longer referenced in the template (they were removed when the native `<select>` was substituted). They constitute dead code and will be automatically resolved once Finding 1 is fixed by restoring the shadcn `<Select>` component.

**Fix:** Either restore the shadcn `<Select>` (preferred — fixes both findings at once) or, if the native `<select>` is deliberately kept, remove all five unused imports.

---

## What Is Working Well

- The core API-alignment fix is correct: `POST /management/workspaces/{workspace_id}/knowledge-graphs` is now the call path and workspace selection is validated before submission.
- The `data-sources/index.vue` fix (`?? []` null-coalescing the `apiFetch` result) is minimal and correct — the backend returns a plain JSON array, not a wrapped object.
- The `tenantVersion` watcher now also clears `workspaces` and `selectedWorkspaceId` on tenant switch, which is the right behaviour.
- The switch from local `apiFetch('/iam/workspaces')` to the shared `useIamApi().listWorkspaces()` composable is a positive code-quality improvement.
- All test scenarios (workspace required, API call uses correct URL, error resets `creating`) are covered and assertions are strong.
- Both commits follow conventional commit format and carry the required trailers.