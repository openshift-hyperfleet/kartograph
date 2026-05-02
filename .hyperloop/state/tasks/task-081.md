---
id: task-081
title: "Data Sources UI — add delete and connection-config update for existing data sources"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps:
  - task-080
round: 0
branch: null
pr: null
pr_title: "feat(ui): add delete and credential-update operations to Data Sources page"
pr_description: |
  ## What & Why

  The spec requires:

  > **Backend API Alignment — Scenario: Resource operations succeed end-to-end**
  > GIVEN an authenticated user
  > WHEN the user performs any **create, read, update, or delete** operation via the UI
  > THEN the corresponding backend API call succeeds (2xx response)
  > AND the UI reflects the updated state without requiring a manual refresh

  The Data Sources page (`src/dev-ui/app/pages/data-sources/index.vue`) currently
  implements **Create** (4-step wizard) and **Read** (list with sync history and ontology
  edit). Both **connection-config Update** and **Delete** are missing from the UI despite
  the backend exposing the routes:

  - `PATCH /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}` — update name
    and/or credentials
  - `DELETE /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}` — remove data
    source and its sync history

  Each data source card currently shows three actions: "Edit Ontology", "Trigger Sync",
  and "View Logs" (inside sync history rows). There is no way for a user to:
  - Update expired credentials (e.g., a GitHub PAT that has rotated)
  - Remove a data source they no longer want

  This PR adds:
  1. An **Edit Config** button on each data source card that opens a side panel to update
     the name and/or credentials (access token) for the data source.
  2. A **Delete** button that opens an `AlertDialog` confirmation warning about loss of
     sync history.

  Both operations refresh the data source list on success (satisfying "UI reflects the
  updated state without requiring a manual refresh").

  ## Spec Requirements Satisfied

  **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
  from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > WHEN the user performs any create, read, **update**, or **delete** operation via the UI
  > THEN the corresponding backend API call succeeds (2xx response)
  > AND the UI reflects the updated state without requiring a manual refresh

  **Requirement: Data Source Connection — Scenario: Credential handling**:

  > GIVEN credentials provided during data source setup
  > WHEN the data source is saved
  > THEN credentials are encrypted and stored server-side
  > AND the plaintext is never persisted in the browser

  The credential-update flow must also honour this: the new credential is submitted to
  the backend (PATCH) immediately; it is never stored in component state beyond the
  ephemeral input value.

  ## Key Design Decisions

  - **Edit Config as a side Sheet (not inline)**: credentials are sensitive; a Sheet
    keeps them isolated and makes it clear the user is in "edit credentials" mode.
    This follows the existing pattern used by the Workspace and Group detail panels.

  - **Credential masking**: the edit form shows an empty token input (placeholder
    `"Leave blank to keep existing"`) so the current credential is never exposed in
    the browser. Only a new value, when entered, is submitted via PATCH.

  - **AlertDialog for delete**: uses the `AlertDialog` component added by `task-080`.
    The confirmation body warns that all sync history will be permanently removed.

  - **data-source-id preserved in list**: after PATCH, the local `dataSources` array
    entry is updated in-place so the UI does not flicker to a loading state.

  - **Frontend-only for delete/PATCH UI**: both backend routes exist and are tested.
    No backend changes are required.

  - **kg_id from data source record**: each `DataSourceResponse` already includes
    `knowledge_graph_id` — the edit and delete handlers use this to construct the
    correct nested API path.

  - **TDD first**: all logic tests and structural tests are written before any
    implementation changes to the Vue file.

  ## Files Affected

  - `src/dev-ui/app/tests/data-sources.test.ts` — new test groups for edit-config and
    delete behaviour (logic tests and structural checks).
  - `src/dev-ui/app/pages/data-sources/index.vue` — add edit-config Sheet state,
    delete AlertDialog state, `openEditConfig`, `handleEditConfig`, `openDeleteDs`,
    `handleDeleteDs`, and the corresponding template sections. Add Edit Config and
    Delete buttons to the per-data-source action row.

  ## How to Verify

  1. `cd src/dev-ui && npm run test` — all new tests pass.
  2. Open the Data Sources page with at least one data source.
  3. Click **Edit Config** → Sheet opens with the data source name pre-filled and an
     empty token field.
  4. Enter a new name and/or a new token, click Save → PATCH is called; list refreshes
     with the new name; success toast appears.
  5. Leave the token field empty and save → PATCH is called with only `name`; token is
     unchanged on the backend.
  6. Click **Delete** → AlertDialog appears warning that sync history will be lost.
  7. Click Confirm → DELETE is called; data source disappears from list; success toast.
  8. Click Cancel on the delete dialog → no API call is made.
  9. Trigger a PATCH or DELETE with a network error → error toast appears; UI state
     resets correctly.

  ## TDD Cycle

  1. Write logic tests for `handleEditConfig` (validation, PATCH call, refresh, credential
     masking, error) — RED.
  2. Write logic tests for `handleDeleteDs` (confirm, cancel, DELETE call, refresh,
     error) — RED.
  3. Write structural tests verifying Edit Config Sheet and delete AlertDialog are present
     in the template — RED.
  4. Implement `openEditConfig`, `handleEditConfig`, `openDeleteDs`, `handleDeleteDs` and
     the two template additions — GREEN.
  5. Run `cd src/dev-ui && npm run test` — all pass.
  6. Commit atomically.

  ## Caveats

  - The adapter type is immutable after creation; the Edit Config sheet does NOT expose
    a field for adapter type.
  - The current credential (access token) is never fetched from the backend for display
    (it is stored encrypted). The token input is always empty on open. This is correct
    per the spec's credential-handling scenario.
  - If the user opens the Edit Config sheet and saves without entering a token, the PATCH
    body should omit `credentials` entirely (not send an empty string) so the backend
    preserves the existing credential. This must be verified in the logic tests.
  - `task-080` (AlertDialog component) must be merged before this task begins.
---

## Spec Coverage

**Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

> GIVEN an authenticated user
> WHEN the user performs any create, read, **update**, or **delete** operation via the UI
> THEN the corresponding backend API call succeeds (2xx response)
> AND the UI reflects the updated state without requiring a manual refresh

**Requirement: Data Source Connection — Scenario: Credential handling**:

> THEN credentials are encrypted and stored server-side
> AND the plaintext is never persisted in the browser

## Gap

### Data Sources page is missing Update (connection config) and Delete UI

**File:** `src/dev-ui/app/pages/data-sources/index.vue`

Each data source card renders three action buttons:

```vue
<Button size="sm" variant="outline" @click="requestOntologyEdit(ds)">
  Edit Ontology
</Button>
<Button size="sm" variant="outline" @click="triggerSync(ds.id)">
  Trigger Sync
</Button>
<!-- (View Logs is inside sync-history rows) -->
```

There is no Edit Config or Delete button. The page has no `handleEditConfig`,
`handleDeleteDs`, edit-config Sheet, or delete confirmation AlertDialog.

**Backend routes that exist but are not wired up in the UI:**

| Method | Path | Purpose |
|--------|------|---------|
| PATCH  | `/management/knowledge-graphs/{kg_id}/data-sources/{ds_id}` | Update name, credentials |
| DELETE | `/management/knowledge-graphs/{kg_id}/data-sources/{ds_id}` | Remove data source |

**Consequence:** A user cannot:
- Rotate expired credentials (e.g., a GitHub PAT) without deleting and recreating the
  entire data source and its sync history.
- Remove a data source they no longer want.

The "update" (connection-config) and "delete" clauses of the Backend API Alignment
scenario are permanently failing for data sources because the UI provides no mechanism
to perform them.

Note: Ontology update (via `requestOntologyEdit`) IS implemented — this task only
covers connection-config update (name, credentials) and hard delete.

## Scope

### TDD — write tests first

Add to `src/dev-ui/app/tests/data-sources.test.ts`:

**Edit Config — logic tests:**

```typescript
describe('Data Sources — Edit Config (update name / credentials)', () => {
  it('opens edit config sheet pre-filled with existing data source name', () => {
    const editConfigOpen = { value: false }
    const editConfigDs = { value: null as null | { id: string; name: string; knowledge_graph_id: string } }
    const editConfigName = { value: '' }
    const editConfigToken = { value: '' }

    function openEditConfig(ds: { id: string; name: string; knowledge_graph_id: string }) {
      editConfigDs.value = ds
      editConfigName.value = ds.name
      editConfigToken.value = '' // never pre-fill the credential
      editConfigOpen.value = true
    }

    openEditConfig({ id: 'ds-1', name: 'My Repo', knowledge_graph_id: 'kg-1' })

    expect(editConfigOpen.value).toBe(true)
    expect(editConfigName.value).toBe('My Repo')
    expect(editConfigToken.value).toBe('') // credential is never pre-filled
    expect(editConfigDs.value?.id).toBe('ds-1')
  })

  it('calls PATCH with name and credentials when token is provided', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      id: 'ds-1', name: 'Updated Repo', knowledge_graph_id: 'kg-1',
    })
    const editConfigDs = { value: { id: 'ds-1', knowledge_graph_id: 'kg-1' } }
    const editConfigName = { value: 'Updated Repo' }
    const editConfigToken = { value: 'ghp_newtoken123' }
    const editConfigOpen = { value: true }
    const saving = { value: false }
    const loadDataSources = vi.fn().mockResolvedValue(undefined)

    async function handleEditConfig() {
      if (!editConfigName.value.trim()) return
      saving.value = true
      try {
        const body: Record<string, unknown> = { name: editConfigName.value.trim() }
        if (editConfigToken.value.trim()) {
          body.credentials = { access_token: editConfigToken.value.trim() }
        }
        await apiFetch(
          `/management/knowledge-graphs/${editConfigDs.value!.knowledge_graph_id}/data-sources/${editConfigDs.value!.id}`,
          { method: 'PATCH', body },
        )
        editConfigOpen.value = false
        await loadDataSources()
      } finally {
        saving.value = false
      }
    }

    await handleEditConfig()

    expect(apiFetch).toHaveBeenCalledWith(
      '/management/knowledge-graphs/kg-1/data-sources/ds-1',
      expect.objectContaining({
        method: 'PATCH',
        body: { name: 'Updated Repo', credentials: { access_token: 'ghp_newtoken123' } },
      }),
    )
    expect(loadDataSources).toHaveBeenCalledOnce()
    expect(editConfigOpen.value).toBe(false)
    expect(saving.value).toBe(false)
  })

  it('omits credentials from PATCH body when token field is empty', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-1', name: 'Updated Repo' })
    const editConfigDs = { value: { id: 'ds-1', knowledge_graph_id: 'kg-1' } }
    const editConfigName = { value: 'Updated Repo' }
    const editConfigToken = { value: '' } // user left token blank
    const saving = { value: false }
    const editConfigOpen = { value: true }

    async function handleEditConfig() {
      saving.value = true
      try {
        const body: Record<string, unknown> = { name: editConfigName.value.trim() }
        if (editConfigToken.value.trim()) {
          body.credentials = { access_token: editConfigToken.value.trim() }
        }
        await apiFetch(
          `/management/knowledge-graphs/${editConfigDs.value!.knowledge_graph_id}/data-sources/${editConfigDs.value!.id}`,
          { method: 'PATCH', body },
        )
        editConfigOpen.value = false
      } finally {
        saving.value = false
      }
    }

    await handleEditConfig()

    const [, options] = apiFetch.mock.calls[0]
    expect(options.body).not.toHaveProperty('credentials')
    expect(options.body).toEqual({ name: 'Updated Repo' })
  })

  it('shows inline error and does not call API when name is empty', async () => {
    const apiFetch = vi.fn()
    const editConfigName = { value: '   ' }
    const editNameError = { value: '' }
    let apiCalled = false

    async function handleEditConfig() {
      editNameError.value = ''
      if (!editConfigName.value.trim()) {
        editNameError.value = 'Data source name is required'
        return
      }
      apiCalled = true
      await apiFetch('/management/knowledge-graphs/kg-1/data-sources/ds-1', {
        method: 'PATCH', body: {},
      })
    }

    await handleEditConfig()

    expect(apiCalled).toBe(false)
    expect(editNameError.value).toBe('Data source name is required')
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('shows error toast and keeps sheet open on PATCH failure', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Forbidden'))
    const editConfigDs = { value: { id: 'ds-1', knowledge_graph_id: 'kg-1' } }
    const editConfigName = { value: 'New Name' }
    const editConfigToken = { value: '' }
    const editConfigOpen = { value: true }
    const saving = { value: false }
    let errorMsg = ''

    async function handleEditConfig() {
      saving.value = true
      try {
        const body: Record<string, unknown> = { name: editConfigName.value.trim() }
        await apiFetch(
          `/management/knowledge-graphs/${editConfigDs.value!.knowledge_graph_id}/data-sources/${editConfigDs.value!.id}`,
          { method: 'PATCH', body },
        )
        editConfigOpen.value = false
      } catch (err) {
        errorMsg = err instanceof Error ? err.message : 'Failed to update'
        // sheet stays open
      } finally {
        saving.value = false
      }
    }

    await handleEditConfig()

    expect(errorMsg).toBe('Forbidden')
    expect(editConfigOpen.value).toBe(true) // still open
    expect(saving.value).toBe(false)
  })
})
```

**Delete — logic tests:**

```typescript
describe('Data Sources — Delete with confirmation', () => {
  it('opens delete AlertDialog with the target data source id and name', () => {
    const deleteDialogOpen = { value: false }
    const deletingDs = { value: null as null | { id: string; name: string; knowledge_graph_id: string } }

    function openDeleteDs(ds: { id: string; name: string; knowledge_graph_id: string }) {
      deletingDs.value = ds
      deleteDialogOpen.value = true
    }

    openDeleteDs({ id: 'ds-1', name: 'My Repo', knowledge_graph_id: 'kg-1' })

    expect(deleteDialogOpen.value).toBe(true)
    expect(deletingDs.value?.id).toBe('ds-1')
    expect(deletingDs.value?.name).toBe('My Repo')
  })

  it('calls DELETE on the correct nested path and refreshes the list', async () => {
    const apiFetch = vi.fn().mockResolvedValue(undefined) // 204
    const deletingDs = { value: { id: 'ds-1', name: 'My Repo', knowledge_graph_id: 'kg-1' } }
    const deleting = { value: false }
    const deleteDialogOpen = { value: true }
    const loadDataSources = vi.fn().mockResolvedValue(undefined)

    async function handleDeleteDs() {
      if (!deletingDs.value) return
      deleting.value = true
      try {
        await apiFetch(
          `/management/knowledge-graphs/${deletingDs.value.knowledge_graph_id}/data-sources/${deletingDs.value.id}`,
          { method: 'DELETE' },
        )
        deleteDialogOpen.value = false
        await loadDataSources()
      } finally {
        deleting.value = false
      }
    }

    await handleDeleteDs()

    expect(apiFetch).toHaveBeenCalledWith(
      '/management/knowledge-graphs/kg-1/data-sources/ds-1',
      { method: 'DELETE' },
    )
    expect(loadDataSources).toHaveBeenCalledOnce()
    expect(deleteDialogOpen.value).toBe(false)
    expect(deleting.value).toBe(false)
  })

  it('does not call DELETE when the dialog is cancelled', () => {
    const apiFetch = vi.fn()
    const deleteDialogOpen = { value: true }

    function cancelDelete() {
      deleteDialogOpen.value = false
    }

    cancelDelete()

    expect(apiFetch).not.toHaveBeenCalled()
    expect(deleteDialogOpen.value).toBe(false)
  })

  it('shows error toast and resets deleting flag on DELETE failure', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Server error'))
    const deletingDs = { value: { id: 'ds-1', knowledge_graph_id: 'kg-1' } }
    const deleting = { value: false }
    const deleteDialogOpen = { value: true }
    let errorMsg = ''

    async function handleDeleteDs() {
      deleting.value = true
      try {
        await apiFetch(
          `/management/knowledge-graphs/${deletingDs.value!.knowledge_graph_id}/data-sources/${deletingDs.value!.id}`,
          { method: 'DELETE' },
        )
        deleteDialogOpen.value = false
      } catch (err) {
        errorMsg = err instanceof Error ? err.message : 'Failed to delete'
        deleteDialogOpen.value = false
      } finally {
        deleting.value = false
      }
    }

    await handleDeleteDs()

    expect(errorMsg).toBe('Server error')
    expect(deleting.value).toBe(false)
  })

  it('does not refresh list when DELETE throws', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Forbidden'))
    const loadDataSources = vi.fn()
    const deletingDs = { value: { id: 'ds-1', knowledge_graph_id: 'kg-1' } }

    async function handleDeleteDs() {
      try {
        await apiFetch(
          `/management/knowledge-graphs/${deletingDs.value!.knowledge_graph_id}/data-sources/${deletingDs.value!.id}`,
          { method: 'DELETE' },
        )
        await loadDataSources()
      } catch {
        // error path
      }
    }

    await handleDeleteDs()

    expect(loadDataSources).not.toHaveBeenCalled()
  })
})
```

**Structural tests:**

```typescript
describe('Data Sources page — edit-config and delete structural checks', () => {
  const dsVue = readFileSync(
    resolve(__dirname, '../pages/data-sources/index.vue'),
    'utf-8',
  )

  it('declares editConfigOpen state', () => {
    expect(dsVue).toMatch(/editConfigOpen/)
  })

  it('declares deleteDialogOpen state (or deleteDsOpen)', () => {
    expect(dsVue).toMatch(/deleteDialogOpen|deleteDsOpen/)
  })

  it('calls PATCH on data-sources/{id} in handleEditConfig', () => {
    expect(dsVue).toMatch(/PATCH.*data-sources|data-sources.*PATCH/)
  })

  it('calls DELETE on data-sources/{id} in handleDeleteDs', () => {
    expect(dsVue).toMatch(/DELETE.*data-sources|data-sources.*DELETE/)
  })

  it('edit config Sheet is present in the template', () => {
    expect(dsVue).toMatch(/editConfigOpen|Edit Config/)
  })

  it('delete AlertDialog is present in the template', () => {
    expect(dsVue).toMatch(/AlertDialog|deleteDialogOpen|deleteDsOpen/)
  })

  it('delete confirmation warns about sync history loss', () => {
    expect(dsVue).toMatch(/sync history|cannot be undone/i)
  })

  it('credential input has placeholder indicating optional re-entry', () => {
    expect(dsVue).toMatch(/Leave blank|keep existing/i)
  })

  it('handleEditConfig omits credentials when token is empty', () => {
    expect(dsVue).toMatch(/trim\(\)|credentials/)
  })
})
```

### Implementation

#### 1. New imports

In the `<script setup>` section of `data-sources/index.vue`, add:

```typescript
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/components/ui/sheet'
import { Settings, Trash2 } from 'lucide-vue-next'
```

#### 2. New state variables

```typescript
// Edit Config (connection configuration update)
const editConfigOpen = ref(false)
const editConfigDs = ref<DataSourceResponse | null>(null)
const editConfigName = ref('')
const editConfigToken = ref('')
const editConfigNameError = ref('')
const savingConfig = ref(false)

// Delete
const deleteDsOpen = ref(false)
const deletingDs = ref<DataSourceResponse | null>(null)
const deletingDsFlag = ref(false)
```

#### 3. `openEditConfig` + `handleEditConfig`

```typescript
function openEditConfig(ds: DataSourceResponse) {
  editConfigDs.value = ds
  editConfigName.value = ds.name
  editConfigToken.value = '' // never pre-fill; credential is server-side only
  editConfigNameError.value = ''
  editConfigOpen.value = true
}

async function handleEditConfig() {
  editConfigNameError.value = ''
  if (!editConfigName.value.trim()) {
    editConfigNameError.value = 'Data source name is required'
    return
  }
  savingConfig.value = true
  try {
    const { apiFetch } = useApiClient()
    const body: Record<string, unknown> = { name: editConfigName.value.trim() }
    if (editConfigToken.value.trim()) {
      body.credentials = { access_token: editConfigToken.value.trim() }
    }
    await apiFetch(
      `/management/knowledge-graphs/${editConfigDs.value!.knowledge_graph_id}/data-sources/${editConfigDs.value!.id}`,
      { method: 'PATCH', body },
    )
    toast.success('Data source updated')
    editConfigOpen.value = false
    await loadDataSources()
  } catch (err) {
    toast.error('Failed to update data source', {
      description: extractErrorMessage(err),
    })
    // sheet stays open so user can retry
  } finally {
    savingConfig.value = false
  }
}
```

#### 4. `openDeleteDs` + `handleDeleteDs`

```typescript
function openDeleteDs(ds: DataSourceResponse) {
  deletingDs.value = ds
  deleteDsOpen.value = true
}

async function handleDeleteDs() {
  if (!deletingDs.value) return
  deletingDsFlag.value = true
  try {
    const { apiFetch } = useApiClient()
    await apiFetch(
      `/management/knowledge-graphs/${deletingDs.value.knowledge_graph_id}/data-sources/${deletingDs.value.id}`,
      { method: 'DELETE' },
    )
    const name = deletingDs.value.name
    toast.success(`Data source "${name}" deleted`)
    deleteDsOpen.value = false
    await loadDataSources()
  } catch (err) {
    toast.error('Failed to delete data source', {
      description: extractErrorMessage(err),
    })
    deleteDsOpen.value = false
  } finally {
    deletingDsFlag.value = false
    deletingDs.value = null
  }
}
```

#### 5. Per-data-source action buttons

Add Edit Config and Delete buttons to the existing action row on each data source card
(alongside the current "Edit Ontology" and "Trigger Sync" buttons):

```vue
<Button size="sm" variant="outline" @click="openEditConfig(ds)">
  <Settings class="mr-1.5 size-3.5" />
  Edit Config
</Button>
<Button
  size="sm"
  variant="outline"
  class="text-destructive hover:bg-destructive/10"
  @click="openDeleteDs(ds)"
>
  <Trash2 class="mr-1.5 size-3.5" />
  Delete
</Button>
```

#### 6. Edit Config Sheet

```vue
<!-- Edit Config Sheet -->
<Sheet v-model:open="editConfigOpen">
  <SheetContent side="right" class="w-full sm:max-w-md">
    <SheetHeader>
      <SheetTitle>Edit Data Source</SheetTitle>
      <SheetDescription>
        Update the name or rotate the access credentials for this data source.
      </SheetDescription>
    </SheetHeader>
    <form class="mt-6 space-y-4" @submit.prevent="handleEditConfig">
      <div class="space-y-1.5">
        <Label for="edit-ds-name">Name <span class="text-destructive">*</span></Label>
        <Input
          id="edit-ds-name"
          v-model="editConfigName"
          placeholder="e.g. my-org/my-repo"
          :disabled="savingConfig"
          @input="editConfigNameError = ''"
        />
        <p v-if="editConfigNameError" class="text-sm text-destructive">{{ editConfigNameError }}</p>
      </div>
      <div class="space-y-1.5">
        <Label for="edit-ds-token">Access Token</Label>
        <Input
          id="edit-ds-token"
          v-model="editConfigToken"
          type="password"
          placeholder="Leave blank to keep existing credential"
          :disabled="savingConfig"
        />
        <p class="text-xs text-muted-foreground">
          The current credential is stored encrypted server-side and is never shown here.
          Enter a new token only if you need to rotate it.
        </p>
      </div>
      <div class="flex justify-end gap-2 pt-2">
        <Button
          type="button"
          variant="outline"
          :disabled="savingConfig"
          @click="editConfigOpen = false"
        >
          Cancel
        </Button>
        <Button type="submit" :disabled="savingConfig || !editConfigName.trim()">
          <Loader2 v-if="savingConfig" class="mr-2 size-4 animate-spin" />
          {{ savingConfig ? 'Saving...' : 'Save' }}
        </Button>
      </div>
    </form>
  </SheetContent>
</Sheet>
```

#### 7. Delete AlertDialog

```vue
<!-- Delete Data Source AlertDialog -->
<AlertDialog v-model:open="deleteDsOpen">
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Delete "{{ deletingDs?.name }}"?</AlertDialogTitle>
      <AlertDialogDescription>
        This will permanently delete the data source and all of its sync history.
        This action cannot be undone.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel :disabled="deletingDsFlag">Cancel</AlertDialogCancel>
      <AlertDialogAction
        class="bg-destructive text-destructive-foreground hover:bg-destructive/90"
        :disabled="deletingDsFlag"
        @click.prevent="handleDeleteDs"
      >
        <Loader2 v-if="deletingDsFlag" class="mr-2 size-4 animate-spin" />
        {{ deletingDsFlag ? 'Deleting...' : 'Delete' }}
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

## Acceptance Criteria

- `PATCH /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}` is called with
  `{ name }` (or `{ name, credentials: { access_token } }` when token is entered).
  On 200, the list refreshes and shows the new name.
- `DELETE /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}` is called on
  confirm. On 204, the data source disappears from the list.
- Edit Config sheet pre-fills the current data source name; the token input is always
  empty (credential is never fetched from the backend for display).
- Leaving the token input empty and saving omits `credentials` from the PATCH body
  entirely — the backend preserves the existing credential.
- Empty name in the edit sheet shows inline error; API is not called.
- Delete AlertDialog warns that sync history will be lost.
- Cancelling the delete dialog makes no API call.
- Success toasts appear for both edit and delete operations.
- Error toasts appear for both operations on API failure; edit sheet stays open on
  failure so the user can retry.
- Both `savingConfig` and `deletingDsFlag` are reset to `false` in all code paths
  (finally block).
- All new unit tests and structural tests pass (`cd src/dev-ui && npm run test`).
- No regressions on the existing Data Sources page tests.
- `task-080` (AlertDialog component) must land first.

## TDD Cycle

1. Write logic tests for `handleEditConfig` (validation, PATCH call, credential-omit
   behaviour, error handling) — RED.
2. Write logic tests for `handleDeleteDs` (confirm, cancel, DELETE call, refresh,
   error) — RED.
3. Write structural tests for edit-config Sheet and delete AlertDialog in the Vue
   file — RED.
4. Implement `openEditConfig`, `handleEditConfig`, `openDeleteDs`, `handleDeleteDs`
   and the two template additions in `data-sources/index.vue` — GREEN.
5. Run `cd src/dev-ui && npm run test` — all pass.
6. Commit atomically.
