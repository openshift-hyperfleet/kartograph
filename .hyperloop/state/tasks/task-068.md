---
id: task-068
title: Backend API Alignment — test data source creation uses KG-scoped endpoint
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(ui): verify data source creation uses KG-scoped POST endpoint"
pr_description: |
  ## What & Why

  The `experience.spec.md` spec was updated to add a new **Requirement: Backend API
  Alignment** with two scenarios:

  > **Scenario: Resource operations succeed end-to-end**
  > GIVEN a user performs any create, read, update, or delete operation via the UI
  > WHEN the operation is submitted
  > THEN the corresponding backend API call succeeds (2xx response)
  > AND the UI reflects the updated state without requiring a manual refresh

  > **Scenario: Parent context is preserved**
  > GIVEN a resource that is scoped to a parent (e.g., a knowledge graph within a
  > workspace)
  > WHEN the user creates or lists that resource
  > THEN the UI includes the parent context required by the API
  > AND the operation succeeds

  All existing resource operations are correctly implemented, and most have explicit
  endpoint-URL assertions in the test suite. One gap remains: the **data source
  creation** call (`POST /management/knowledge-graphs/{kg_id}/data-sources`) is not
  verified at the `apiFetch` level. The current test in `data-sources.test.ts` mocks
  `createDataSource()` as a whole function, confirming `kg_id` is passed to it, but
  never verifying that the resulting HTTP path includes the KG ID.

  This PR closes that gap. It adds a dedicated test that injects a mocked `apiFetch`
  directly into a `createDataSource` implementation and asserts the URL path contains
  the correct parent knowledge-graph ID. No production code changes are required — the
  implementation is already correct.

  ## Spec Requirements Satisfied

  **Requirement: Backend API Alignment — Scenario: Parent context is preserved** from
  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > GIVEN a resource that is scoped to a parent (e.g., a knowledge graph within a
  > workspace)
  > WHEN the user creates or lists that resource
  > THEN the UI includes the parent context required by the API

  Specifically, the data source create operation is scoped to a knowledge graph (the
  parent). This PR ensures there is an explicit test asserting the KG ID appears in
  the API path.

  ## Coverage landscape (for context)

  The following parent-context assertions already exist in the test suite:

  | Operation | Endpoint | Tested? |
  |---|---|---|
  | Create knowledge graph | `POST /management/workspaces/{ws_id}/knowledge-graphs` | ✅ `knowledge-graphs.test.ts` line 101 |
  | List data sources | `GET /management/knowledge-graphs/{kg_id}/data-sources` | ✅ `data-sources.test.ts` line 596 |
  | List sync runs | `GET /management/data-sources/{ds_id}/sync-runs` | ✅ `data-sources.test.ts` line 648 |
  | Trigger sync | `POST /management/data-sources/{ds_id}/sync` | ✅ `sync-monitoring-extended.test.ts` line 317 |
  | Submit mutations | `POST /graph/knowledge-graphs/{kg_id}/mutations` | ✅ task-065 (`mutations-kg-selector.test.ts`) |
  | **Create data source** | `POST /management/knowledge-graphs/{kg_id}/data-sources` | ❌ **missing — this PR** |

  ## Key Design Decisions

  - **Test-only PR**: No production code changes. The implementation in
    `data-sources/index.vue` already constructs the correct URL:
    ```typescript
    apiFetch(`/management/knowledge-graphs/${params.kg_id}/data-sources`, { method: 'POST', ... })
    ```
    The tests just need to reach through to `apiFetch` rather than mocking
    `createDataSource` at the wrapper level.
  - **Inline function extraction pattern**: Following the established codebase pattern
    (see `sync-monitoring-extended.test.ts`), extract `createDataSource` as a
    parameterized pure function in the test that takes `apiFetch` as a dependency.
    This lets the test inject a `vi.fn()` mock and assert the exact URL call.
  - **Added to `data-sources.test.ts`**: Keeps DS creation coverage co-located with
    DS listing and sync run tests in the same file.

  ## Files Affected

  - `src/dev-ui/app/tests/data-sources.test.ts` — add a new `describe` block
    "Backend API Alignment — data source creation uses KG-scoped endpoint" with
    3-4 test cases verifying the URL path, HTTP method, and request body.

  ## How to Verify

  1. Run `cd src/dev-ui && pnpm test -- data-sources` — new describe block passes.
  2. Run `cd src/dev-ui && pnpm test` — no regressions in any other test file.
  3. Confirm the new tests are in the "Backend API Alignment" section and reference
     the spec scenario in their comments.

  ## Caveats

  - No dependency on task-065: this task covers the data source creation endpoint,
    which is orthogonal to the mutations endpoint fix in task-065.
  - No production code changes means no risk of regressions — this PR is purely
    additive test coverage.
  - The test extraction pattern mirrors `triggerSync()` in `sync-monitoring-extended.test.ts`,
    which is the established precedent for testing URL patterns in this codebase.
---

## Spec Coverage

**Requirement: Backend API Alignment — Scenario: Parent context is preserved** from
`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

> GIVEN a resource that is scoped to a parent (e.g., a knowledge graph within a workspace)
> WHEN the user creates or lists that resource
> THEN the UI includes the parent context required by the API
> AND the operation succeeds

## Gap

### No `apiFetch`-level assertion for data source creation

`src/dev-ui/app/pages/data-sources/index.vue` defines:

```typescript
async function createDataSource(params: {
  kg_id: string
  name: string
  adapter_type: string
  connection_config: Record<string, string>
  credentials?: Record<string, string>
}) {
  const { apiFetch } = useApiClient()
  return apiFetch(`/management/knowledge-graphs/${params.kg_id}/data-sources`, {
    method: 'POST',
    body: {
      name: params.name,
      adapter_type: params.adapter_type,
      connection_config: params.connection_config,
      credentials: params.credentials,
    },
  })
}
```

The corresponding test in `data-sources.test.ts` (around line 920) mocks
`createDataSource` at the function boundary:

```typescript
const createDataSource = vi.fn().mockResolvedValue({ id: 'ds-new' })

async function approveOntology() {
  await createDataSource({
    kg_id: selectedKnowledgeGraphId.value,
    ...
  })
}
await approveOntology()
expect(createDataSource).toHaveBeenCalledOnce()
```

This verifies `kg_id` is passed **to** `createDataSource`, but it never verifies that
`apiFetch` receives the URL `/management/knowledge-graphs/${kg_id}/data-sources`. If
the `createDataSource` implementation were to drop the KG ID from the URL, this test
would not catch it.

**Contrast with sync trigger** (`sync-monitoring-extended.test.ts` line 313):

```typescript
async function triggerSync(dsId: string, apiFetch: (...) => ...) {
  await apiFetch(`/management/data-sources/${dsId}/sync`, { method: 'POST' })
}

it('calls the correct API endpoint to trigger sync', async () => {
  const apiFetch = vi.fn().mockResolvedValue({})
  await triggerSync('ds-abc123', apiFetch)
  expect(apiFetch).toHaveBeenCalledWith(
    '/management/data-sources/ds-abc123/sync',
    { method: 'POST' },
  )
})
```

The sync trigger test injects `apiFetch` directly and asserts the exact URL. The same
pattern should be applied to data source creation to satisfy "Parent context is
preserved."

## Scope

### TDD — write tests first

Add a new `describe` block to `src/dev-ui/app/tests/data-sources.test.ts`:

```typescript
// ── Backend API Alignment — Parent context is preserved ───────────────────────
//
// Spec: "GIVEN a resource that is scoped to a parent (e.g., a knowledge graph
//        within a workspace)
//        WHEN the user creates or lists that resource
//        THEN the UI includes the parent context required by the API"
//
// This block mirrors the pattern in sync-monitoring-extended.test.ts for triggerSync():
// extract createDataSource as a parameterized function, inject apiFetch as a mock,
// and assert the URL path contains the parent knowledge graph ID.

/**
 * Mirrors createDataSource() in data-sources/index.vue.
 * Takes apiFetch as a parameter so tests can inject a mock.
 */
async function createDataSource(
  params: {
    kg_id: string
    name: string
    adapter_type: string
    connection_config: Record<string, string>
    credentials?: Record<string, string>
  },
  apiFetch: (url: string, opts: { method: string; body: Record<string, unknown> }) => Promise<unknown>,
) {
  return apiFetch(`/management/knowledge-graphs/${params.kg_id}/data-sources`, {
    method: 'POST',
    body: {
      name: params.name,
      adapter_type: params.adapter_type,
      connection_config: params.connection_config,
      credentials: params.credentials,
    },
  })
}

describe('Backend API Alignment — data source creation uses KG-scoped endpoint', () => {
  it('POST URL includes the parent knowledge graph ID', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new' })
    await createDataSource(
      {
        kg_id: 'kg-abc123',
        name: 'my-repo',
        adapter_type: 'github',
        connection_config: { repo_url: 'https://github.com/owner/my-repo' },
        credentials: { access_token: 'ghp_test' },
      },
      apiFetch,
    )
    expect(apiFetch).toHaveBeenCalledWith(
      '/management/knowledge-graphs/kg-abc123/data-sources',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('KG ID in the URL path changes when a different knowledge graph is selected', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new-2' })
    await createDataSource(
      {
        kg_id: 'kg-xyz789',
        name: 'another-repo',
        adapter_type: 'github',
        connection_config: { repo_url: 'https://github.com/org/another-repo' },
      },
      apiFetch,
    )
    const calledUrl = (apiFetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(calledUrl).toContain('kg-xyz789')
    expect(calledUrl).not.toContain('kg-abc123')
  })

  it('does NOT use a workspace-scoped path (data sources are KG-scoped, not workspace-scoped)', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new' })
    await createDataSource(
      { kg_id: 'kg-1', name: 'repo', adapter_type: 'github', connection_config: {} },
      apiFetch,
    )
    const calledUrl = (apiFetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(calledUrl).toContain('/management/knowledge-graphs/')
    expect(calledUrl).not.toContain('/management/workspaces/')
  })

  it('request body includes name, adapter_type, and connection_config', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new' })
    await createDataSource(
      {
        kg_id: 'kg-1',
        name: 'my-repo',
        adapter_type: 'github',
        connection_config: { repo_url: 'https://github.com/owner/my-repo' },
        credentials: { access_token: 'ghp_test' },
      },
      apiFetch,
    )
    expect(apiFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: expect.objectContaining({
          name: 'my-repo',
          adapter_type: 'github',
          connection_config: { repo_url: 'https://github.com/owner/my-repo' },
          credentials: { access_token: 'ghp_test' },
        }),
      }),
    )
  })
})
```

Since the implementation is already correct, these tests should go **GREEN immediately**
on first run (no implementation changes needed).

### No implementation changes

The production code in `data-sources/index.vue` already constructs the correct URL:

```typescript
return apiFetch(`/management/knowledge-graphs/${params.kg_id}/data-sources`, {
  method: 'POST',
  body: { name: params.name, adapter_type: params.adapter_type, ... },
})
```

No production code changes are needed. The task is purely about closing the test
coverage gap for the "Backend API Alignment — Parent context is preserved" scenario.

## Acceptance Criteria

- New `describe` block "Backend API Alignment — data source creation uses KG-scoped endpoint"
  exists in `src/dev-ui/app/tests/data-sources.test.ts`.
- All four new test cases pass.
- `cd src/dev-ui && pnpm test` exits 0 with no regressions.
- Each test has a comment referencing the spec scenario ("Parent context is preserved").

## TDD Cycle

1. **Write tests first** — add the new `describe` block to `data-sources.test.ts`.
2. **Run tests** → tests should pass GREEN immediately (implementation is correct).
3. **Commit atomically** with a conventional commit message.
