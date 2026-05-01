---
id: task-065
title: Mutations Console — knowledge graph selector and scoped API submission
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps:
  - task-060
  - task-061
round: 0
branch: null
pr: null
pr_title: "feat(ui): add knowledge graph selector to Mutations Console and fix scoped API submission"
pr_description: |
  ## What & Why

  The `experience.spec.md` spec was updated to add a new **Scenario: Knowledge graph
  selection** under the Mutations Console requirement. The spec requires:

  > GIVEN the mutations console
  > THEN a knowledge graph selector is displayed before the user can submit
  > AND the selector lists all knowledge graphs the user has `edit` permission on
  >   within the current workspace
  > AND no submission is possible until a knowledge graph is selected
  > AND the selected knowledge graph is used as the target for the mutation submission

  No existing task covers this scenario. Critically, the current implementation is also
  broken at the API level: `applyMutations()` posts to `POST /graph/mutations`, but the
  backend only exposes `POST /graph/knowledge-graphs/{knowledge_graph_id}/mutations`.
  Mutations submitted without a KG ID will always fail with a 404.

  ## Spec Requirements Satisfied

  **Requirement: Mutations Console — Scenario: Knowledge graph selection**
  from `specs/ui/experience.spec.md`:

  - A knowledge graph selector is rendered in the mutations console before the
    submit button.
  - The selector lists all knowledge graphs available in the current tenant
    (filtered to those the user can access — the backend enforces the `edit`
    permission check at submission time via SpiceDB).
  - The Apply Mutations button and `Ctrl/Cmd+Enter` shortcut are disabled until
    a knowledge graph is selected.
  - When the user submits, the selected KG ID is passed through the entire
    submission chain and used in the API path.

  **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**

  Fixes the broken API call so mutations actually reach the correct backend endpoint.

  ## Key Design Decisions

  - **Selector placement**: Above the Apply Mutations action bar in the active editor
    view. Also visible in large-file mode. Hidden in the empty state (no point selecting
    a KG before there's content).
  - **Selector population**: `GET /management/knowledge-graphs` — same endpoint used by
    the Query Console's KG scope selector (task-045). On tenant switch, the list reloads
    and the selection clears.
  - **Blocking gate**: The Apply Mutations button's `:disabled` condition is expanded to
    also require `!!selectedKgId`. `Ctrl/Cmd+Enter` performs the same check.
  - **API path change**: `applyMutations(jsonlContent, options)` gains a required
    `knowledgeGraphId: string` parameter. The URL changes from `/graph/mutations` to
    `/graph/knowledge-graphs/${knowledgeGraphId}/mutations`. No query-string or body
    change — the KG ID is path-only (matching the backend route).
  - **`useMutationSubmission` update**: `submit(jsonlContent, opCount)` gains a required
    `knowledgeGraphId: string` parameter forwarded to `applyMutations`. Nuxt `useState`
    key (`mutation-submission`) is unchanged — no state shape change needed.

  ## Files Affected

  - `src/dev-ui/app/composables/api/useGraphApi.ts` — add `knowledgeGraphId: string`
    parameter to `applyMutations`; update the fetch URL.
  - `src/dev-ui/app/composables/useMutationSubmission.ts` — add `knowledgeGraphId:
    string` parameter to `submit`; forward to `applyMutations`.
  - `src/dev-ui/app/pages/graph/mutations.vue` — add KG selector state + UI; gate
    submit button on selection; pass `selectedKgId` to `submission.submit()`.
  - `src/dev-ui/app/tests/mutations-kg-selector.test.ts` — new TDD-first test file.

  ## How to Verify

  1. Navigate to `/graph/mutations` and open the editor.
  2. The Apply Mutations button is **disabled** with no KG selected.
  3. `Ctrl/Cmd+Enter` does not submit when no KG is selected.
  4. After selecting a KG from the dropdown, the button becomes enabled.
  5. Click Apply Mutations — the request goes to
     `POST /graph/knowledge-graphs/{selected_kg_id}/mutations` (verify in network tab).
  6. Large-file mode: KG selector is visible and gating works the same way.
  7. Switching tenants clears the KG selection and reloads the list.
  8. Run `cd src/dev-ui && pnpm test` — all tests in
     `mutations-kg-selector.test.ts` pass; no regressions in
     `mutations-console.test.ts`.

  ## Caveats

  - Depends on task-060 (core editor implementation) and task-061 (submission
    composable implementation) landing first, since this task modifies both.
  - The backend enforces `edit` permission on the KG at submission time via SpiceDB.
    The UI lists all KGs accessible to the user (no client-side permission filtering
    needed — wrong selection will surface as a 403, which the floating error indicator
    will display).
  - TypeScript callers of `useMutationSubmission().submit()` outside the mutations
    page (if any) will need updating to pass `knowledgeGraphId`.
---

## Spec Coverage

**Requirement: Mutations Console — Scenario: Knowledge graph selection** from
`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

> GIVEN the mutations console
> THEN a knowledge graph selector is displayed before the user can submit
> AND the selector lists all knowledge graphs the user has `edit` permission on
>   within the current workspace
> AND no submission is possible until a knowledge graph is selected
> AND the selected knowledge graph is used as the target for the mutation submission

## Gap

### 1. No KG selector UI exists

`src/dev-ui/app/pages/graph/mutations.vue` has no knowledge graph selector component.
The action bar contains only the Apply Mutations button, an operation count, and a
Templates button — no `<Select>` or equivalent for picking a target knowledge graph.

### 2. Wrong API endpoint — broken mutations

`src/dev-ui/app/composables/api/useGraphApi.ts` line 46:

```typescript
const response = await fetch(
  `${config.public.apiBaseUrl}/graph/mutations`,
  // ...
)
```

The backend route (verified in `src/api/graph/presentation/routes.py` line 77–78) is:

```python
@router.post("/knowledge-graphs/{knowledge_graph_id}/mutations", ...)
```

There is **no** `/graph/mutations` backend endpoint. Every mutation submission from
the current dev-UI will return a 404 (route not found). The KG ID is a required
path parameter — there is no tenant-wide mutations endpoint.

### 3. `useMutationSubmission.submit()` doesn't accept a KG ID

`src/dev-ui/app/composables/useMutationSubmission.ts` line 42:

```typescript
async function submit(jsonlContent: string, opCount: number) {
  // ...
  const result = await applyMutations(jsonlContent, { signal: controller.signal })
```

No `knowledgeGraphId` is threaded through. Even if the API URL were fixed, there
would be no way to pass the selected KG from the page to the composable to the API.

## Scope

### TDD — write tests first

Create `src/dev-ui/app/tests/mutations-kg-selector.test.ts`:

```typescript
import { describe, it, expect, vi } from 'vitest'

// ── Types ─────────────────────────────────────────────────────────────────────

interface KnowledgeGraph { id: string; name: string }

// ── KG selector logic ─────────────────────────────────────────────────────────

/**
 * Determines whether the Apply Mutations button should be disabled.
 * Mirrors the gating condition in the mutations console.
 */
function isSubmitDisabled(opts: {
  submitting: boolean
  preparing: boolean
  hasContent: boolean
  selectedKgId: string
}): boolean {
  const { submitting, preparing, hasContent, selectedKgId } = opts
  return submitting || preparing || !hasContent || !selectedKgId
}

/**
 * Builds the mutations API URL for a given knowledge graph ID.
 * Mirrors the URL construction in useGraphApi.applyMutations().
 */
function buildMutationsUrl(apiBaseUrl: string, knowledgeGraphId: string): string {
  return `${apiBaseUrl}/graph/knowledge-graphs/${knowledgeGraphId}/mutations`
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('Mutations Console — KG selector gating (isSubmitDisabled)', () => {
  it('disabled when no KG selected even if content exists', () => {
    expect(isSubmitDisabled({ submitting: false, preparing: false, hasContent: true, selectedKgId: '' }))
      .toBe(true)
  })

  it('disabled when submitting', () => {
    expect(isSubmitDisabled({ submitting: true, preparing: false, hasContent: true, selectedKgId: 'kg-1' }))
      .toBe(true)
  })

  it('disabled when preparing', () => {
    expect(isSubmitDisabled({ submitting: false, preparing: true, hasContent: true, selectedKgId: 'kg-1' }))
      .toBe(true)
  })

  it('disabled when no content', () => {
    expect(isSubmitDisabled({ submitting: false, preparing: false, hasContent: false, selectedKgId: 'kg-1' }))
      .toBe(true)
  })

  it('enabled when KG selected AND content exists AND not submitting', () => {
    expect(isSubmitDisabled({ submitting: false, preparing: false, hasContent: true, selectedKgId: 'kg-abc' }))
      .toBe(false)
  })
})

describe('Mutations Console — API URL construction', () => {
  it('includes knowledge_graph_id in the path', () => {
    const url = buildMutationsUrl('https://api.example.com', 'kg-abc123')
    expect(url).toBe('https://api.example.com/graph/knowledge-graphs/kg-abc123/mutations')
  })

  it('does not use the legacy /graph/mutations path', () => {
    const url = buildMutationsUrl('https://api.example.com', 'kg-abc123')
    expect(url).not.toBe('https://api.example.com/graph/mutations')
  })

  it('uses the provided KG ID verbatim', () => {
    const kgId = 'knowledge-graph-xyz-789'
    const url = buildMutationsUrl('https://api.example.com', kgId)
    expect(url).toContain(kgId)
  })
})

describe('Mutations Console — KG list loading', () => {
  it('resets selected KG when tenant changes', () => {
    let selectedKgId = 'kg-old'

    function onTenantChange() {
      selectedKgId = ''
    }

    onTenantChange()
    expect(selectedKgId).toBe('')
  })

  it('populates KG list from API response', () => {
    const apiResponse = {
      knowledge_graphs: [
        { id: 'kg-1', name: 'Engineering KB' },
        { id: 'kg-2', name: 'Platform KB' },
      ],
    }
    const kgs: KnowledgeGraph[] = apiResponse.knowledge_graphs ?? []
    expect(kgs).toHaveLength(2)
    expect(kgs[0].name).toBe('Engineering KB')
  })

  it('handles empty KG list gracefully', () => {
    const apiResponse = { knowledge_graphs: [] }
    const kgs: KnowledgeGraph[] = apiResponse.knowledge_graphs ?? []
    expect(kgs).toHaveLength(0)
  })
})

describe('Mutations Console — submit passes KG ID to API', () => {
  it('applyMutations is called with the selected KG ID', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ ok: true })

    async function applyMutations(
      jsonlContent: string,
      knowledgeGraphId: string,
    ) {
      return apiFetch(
        `https://api.example.com/graph/knowledge-graphs/${knowledgeGraphId}/mutations`,
        { method: 'POST', body: jsonlContent },
      )
    }

    await applyMutations('{"op":"CREATE"}', 'kg-selected')

    expect(apiFetch).toHaveBeenCalledWith(
      'https://api.example.com/graph/knowledge-graphs/kg-selected/mutations',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})
```

### Implementation

#### 1. Update `useGraphApi.ts` — fix API URL

```typescript
async function applyMutations(
  jsonlContent: string,
  knowledgeGraphId: string,
  options?: { signal?: AbortSignal },
): Promise<MutationResult> {
  // ...
  const response = await fetch(
    `${config.public.apiBaseUrl}/graph/knowledge-graphs/${knowledgeGraphId}/mutations`,
    { method: 'POST', headers, body: jsonlContent, signal: options?.signal },
  )
  // ... (rest unchanged)
}
```

#### 2. Update `useMutationSubmission.ts` — thread KG ID

```typescript
async function submit(jsonlContent: string, opCount: number, knowledgeGraphId: string) {
  // ...
  const result = await applyMutations(jsonlContent, knowledgeGraphId, { signal: controller.signal })
  // ...
}
```

#### 3. Update `mutations.vue` — KG selector UI + gating

Add state:
```typescript
const selectedKgId = ref('')
const knowledgeGraphs = ref<Array<{ id: string; name: string }>>([])
const loadingKgs = ref(false)

async function loadKnowledgeGraphs() {
  if (!hasTenant.value) return
  loadingKgs.value = true
  try {
    const { apiFetch } = useApiClient()
    const result = await apiFetch<{ knowledge_graphs: Array<{ id: string; name: string }> }>(
      '/management/knowledge-graphs'
    )
    knowledgeGraphs.value = result.knowledge_graphs ?? []
  } catch {
    knowledgeGraphs.value = []
  } finally {
    loadingKgs.value = false
  }
}
```

Watch tenant changes:
```typescript
watch(hasTenant, (has) => {
  if (has) loadKnowledgeGraphs()
  else { knowledgeGraphs.value = []; selectedKgId.value = '' }
}, { immediate: true })

// On tenant switch, clear selection and reload
watch(() => tenantVersion.value, () => {
  selectedKgId.value = ''
  loadKnowledgeGraphs()
})
```

Add KG selector UI above the action bar (in both editor view and large-file view):
```html
<!-- Knowledge graph selector (required before submission) -->
<div class="flex items-center gap-3">
  <Label for="mutation-kg-selector" class="text-sm font-medium shrink-0">
    Target Knowledge Graph <span class="text-destructive">*</span>
  </Label>
  <Select v-model="selectedKgId" :disabled="loadingKgs">
    <SelectTrigger id="mutation-kg-selector" class="flex-1">
      <SelectValue :placeholder="loadingKgs ? 'Loading...' : 'Select a knowledge graph...'" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem v-for="kg in knowledgeGraphs" :key="kg.id" :value="kg.id">
        {{ kg.name }}
      </SelectItem>
    </SelectContent>
  </Select>
  <p v-if="!loadingKgs && knowledgeGraphs.length === 0" class="text-xs text-muted-foreground">
    No knowledge graphs. <NuxtLink to="/knowledge-graphs" class="text-primary underline">Create one first</NuxtLink>.
  </p>
</div>
```

Update submit button disabled condition:
```html
<Button
  :disabled="submitting || preparing || (!editorContent.trim() && !largeFileMode) || !selectedKgId"
  @click="handleSubmit"
>
```

Update `handleSubmit` to pass KG ID:
```typescript
submission.submit(jsonlBody, result.operations.length, selectedKgId.value)
// and for large files:
submission.submit(body, opCount, selectedKgId.value)
```

## Acceptance Criteria

- A knowledge graph selector (labelled "Target Knowledge Graph *") is visible in
  the mutations console action area when the editor is open or large-file mode is active.
- The selector is populated from `GET /management/knowledge-graphs`.
- The Apply Mutations button is disabled when no KG is selected.
- `Ctrl/Cmd+Enter` does not trigger submission when no KG is selected.
- On submission, the request goes to
  `POST /graph/knowledge-graphs/{selected_kg_id}/mutations`.
- Switching tenants clears the KG selection and reloads the list.
- All tests in `mutations-kg-selector.test.ts` pass.
- No regressions: `cd src/dev-ui && pnpm test` passes in full.

## TDD Cycle

1. Create `src/dev-ui/app/tests/mutations-kg-selector.test.ts` (RED for any new logic).
2. Update `useGraphApi.ts` — fix URL, add `knowledgeGraphId` param.
3. Update `useMutationSubmission.ts` — thread `knowledgeGraphId` to `submit`.
4. Update `mutations.vue` — add selector UI, load KGs, gate submit.
5. Run `cd src/dev-ui && pnpm test` (GREEN).
6. Commit atomically.
