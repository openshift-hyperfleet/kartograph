---
task_id: task-014
round: 2
role: verifier
verdict: fail
---
## Verification Summary

| Check | Result | Detail |
|---|---|---|
| Unit tests (2051) | PASS | All pass, 0 failures |
| Ruff linting | PASS | Zero violations |
| Ruff formatting | PASS | 452 files formatted |
| Mypy type checking | PASS | Zero errors in 452 source files |
| Architecture boundary tests (40) | PASS | All pass |
| check-frontend-tests-exist | PASS | 2 test files found |
| check-frontend-test-infrastructure | PASS | vitest in package.json |
| check-no-coming-soon-stubs (dev-ui) | PASS | No stub markers in project source |
| check-no-future-placeholder-comments (dev-ui) | PASS | No placeholders in project source |
| Frontend tests runnable | **FAIL** | vitest@^2.2.5 doesn't exist; pnpm install fails |
| Sync monitoring data loading | **FAIL** | loadDataSources() is a stub; UI always empty |

---

## FAIL 1 — vitest@^2.2.5 Is Not a Valid Package Version

`src/dev-ui/package.json` specifies `"vitest": "^2.2.5"` in devDependencies.
This version does not exist in the npm registry. The vitest 2.x series topped at
`2.1.9`; the next release was `3.x` and the current latest is `4.1.5`.

**Confirmed by:**
```
$ cd src/dev-ui && pnpm install
ERR_PNPM_NO_MATCHING_VERSION  No matching version found for vitest@^2.2.5
The latest release of vitest is "4.1.5".
```

**Consequence:** `pnpm install` fails. No `node_modules` is installed. The vitest
test scripts cannot be run at all — the tests have never been executed. The
`pnpm-lock.yaml` confirms this: vitest does not appear anywhere in the lock file,
meaning it was never successfully resolved.

The `check-frontend-test-infrastructure.sh` script only checks whether the string
`"vitest"` appears in `package.json` (it does), so it passes superficially — but
the actual dependency is broken.

**Required fix:** Update `package.json` to a valid version range, e.g.:
```json
"vitest": "^2.1.9"
```
or update to the current major:
```json
"vitest": "^4.1.5"
```
After fixing, run `pnpm install` and `pnpm test` to verify all 13 tests pass.

---

## FAIL 2 — loadDataSources() Is a Stub; Sync Monitoring UI Never Populated

`src/dev-ui/app/pages/data-sources/index.vue` lines 494–498:

```typescript
async function loadDataSources() {
  // Data sources are loaded per-KG, but for this view we show all.
  // When management routes are available, they'll be fetched from the API.
  dataSources.value = []
}
```

This function always sets `dataSources` to an empty array without calling any API.
The comment "When management routes are available, they'll be fetched from the API"
is incorrect — the management routes **are** available in the same PR
(`GET /management/knowledge-graphs/{kg_id}/data-sources`,
`GET /management/data-sources/{ds_id}/sync-runs`). The function was never wired up.

Additionally, `loadDataSources()` is never called on component mount — there is no
`onMounted` hook. It is only called inside `triggerSync()` after a sync is triggered.
So even if the function were implemented, the data source list would not be populated
on initial page load.

**Consequence:** The `dataSources` ref is always empty. The data source card list
(lines 562–603 of the template) is never rendered. All four Sync Monitoring spec
scenarios remain non-functional in practice:

- **Active sync progress** — no cards rendered, status badges never shown
- **Sync history** — no cards rendered, run history never shown
- **Sync logs** — (not implemented, but irrelevant while cards are invisible)
- **Manual sync trigger** — `triggerSync()` is wired but never reachable from UI

**Required fix:**

1. Add a `GET /management/knowledge-graphs` + per-KG `GET .../data-sources` fetch
   sequence in `loadDataSources()`, or add a new tenant-wide data source listing
   endpoint to the management backend. Either approach is acceptable.
2. Call `loadDataSources()` from an `onMounted` hook (and when the tenant changes).

Example skeleton:
```typescript
import { onMounted } from 'vue'

async function loadDataSources() {
  loadingDataSources.value = true
  try {
    const { apiFetch } = useApiClient()
    // Option A: fetch per-KG (requires listing KGs first)
    const { knowledge_graphs } = await apiFetch<{ knowledge_graphs: Array<{id: string}> }>(
      '/management/knowledge-graphs'
    )
    const all: DataSourceItem[] = []
    for (const kg of knowledge_graphs) {
      const items = await apiFetch<DataSourceItem[]>(
        `/management/knowledge-graphs/${kg.id}/data-sources`
      )
      all.push(...items)
    }
    dataSources.value = all
  } catch {
    dataSources.value = []
  } finally {
    loadingDataSources.value = false
  }
}

onMounted(() => { loadDataSources() })
```

---

## Secondary Observation — Check Scripts Fail Against src/ Due to .venv

`check-no-coming-soon-stubs.sh` and `check-no-future-placeholder-comments.sh` both
exit 1 when run against the default `src/` directory because they scan
`src/api/.venv/` (third-party package sources). The scripts exclude `node_modules`,
`__pycache__`, `.git`, `dist`, and `.nuxt` — but NOT `.venv`.

This is a **script deficiency**, not a project code issue. The project's own source
is clean when checked against `src/dev-ui/`. Since `.venv` is in `.gitignore`, CI
will not see false positives. However, local verification is misleading.

**Recommended fix (non-blocking):** Add `--exclude-dir=.venv` to the grep invocation
in both scripts to make local and CI results consistent.

---

## Required Fixes Before Re-submission

1. **Fix vitest version constraint:** Change `"vitest": "^2.2.5"` to
   `"vitest": "^2.1.9"` (or `"^4.1.5"`) in `src/dev-ui/package.json`, run
   `pnpm install`, and verify all 13 frontend tests pass with `pnpm test`.

2. **Implement loadDataSources():** Replace the stub body with a real API call,
   wire it to `onMounted`, and verify the data source card list renders correctly
   with real data from the management API.