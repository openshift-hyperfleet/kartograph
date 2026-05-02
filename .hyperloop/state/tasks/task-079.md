---
id: task-079
title: "Knowledge Graphs UI — add inline edit (rename/re-describe) and delete with confirmation"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(ui): add edit and delete operations to Knowledge Graphs page"
pr_description: |
  ## What & Why

  The spec requires:

  > **Backend API Alignment — Scenario: Resource operations succeed end-to-end**
  > GIVEN an authenticated user
  > WHEN the user performs any **create, read, update, or delete** operation via the UI
  > THEN the corresponding backend API call succeeds (2xx response)
  > AND the UI reflects the updated state without requiring a manual refresh

  The Knowledge Graphs page (`src/dev-ui/app/pages/knowledge-graphs/index.vue`)
  currently implements only **Create** and **Read**. Both **Update** and **Delete**
  are missing from the UI despite the backend having the routes:

  - `PATCH /management/knowledge-graphs/{kg_id}` — update name/description
  - `DELETE /management/knowledge-graphs/{kg_id}` — delete with cascade

  Each KG card shows only "Add Data Source" and "Query" action buttons. There is no
  way for a user to rename a KG or delete it — making the "update" and "delete"
  clauses of the Backend API Alignment scenario unreachable.

  This PR adds:
  1. An **Edit** button on each KG card that opens a pre-filled dialog to rename/re-describe.
  2. A **Delete** button that opens an `AlertDialog` confirmation warning of cascade deletion.

  Both operations refresh the list on success (satisfying "UI reflects the updated
  state without requiring a manual refresh").

  ## Spec Requirements Satisfied

  **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
  from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > WHEN the user performs any create, read, **update**, or **delete** operation via the UI
  > THEN the corresponding backend API call succeeds (2xx response)
  > AND the UI reflects the updated state without requiring a manual refresh

  ## Key Design Decisions

  - **Edit dialog (not inline)**: A modal dialog pre-filled with the existing name and
    description matches the established create-dialog pattern. Inline editing
    (contenteditable) is harder to test and inconsistent with the rest of the UI.

  - **AlertDialog for delete**: shadcn/vue `AlertDialog` is the correct component for
    destructive confirmations. The dialog body warns explicitly that all connected
    data sources will also be deleted (cascade).

  - **Optimistic refresh**: Both `handleEdit` and `handleDelete` call `loadKnowledgeGraphs()`
    inside the `try` block after a successful API call — identical to the `handleCreate`
    pattern already in the file.

  - **Frontend-only**: No backend changes. Both endpoints exist and are tested.

  - **TDD first**: Unit tests for `handleEdit` and `handleDelete` logic (validation,
    API call shape, refresh, error handling) and structural tests verifying the Vue
    template contains the expected elements — all written before implementation.

  ## Files Affected

  - `src/dev-ui/app/tests/knowledge-graphs.test.ts` — new test groups for edit and
    delete behaviour (logic tests + one structural test group).
  - `src/dev-ui/app/pages/knowledge-graphs/index.vue` — add edit state, delete state,
    `handleEdit`, `handleDelete`, edit dialog, delete `AlertDialog`, and per-card action
    buttons.

  ## How to Verify

  1. `cd src/dev-ui && npm run test` — all new tests pass.
  2. Open the Knowledge Graphs page with at least one KG.
  3. Click the **Edit** (pencil) button → dialog opens pre-filled with name and description.
  4. Change the name and click Save → list refreshes with new name; success toast shown.
  5. Click the **Delete** (trash) button → AlertDialog appears with cascade warning.
  6. Click Confirm → KG disappears from list; success toast shown.
  7. During delete, clicking Cancel aborts without any API call.
  8. Trigger a name conflict (duplicate name) → 409 error toast appears.

  ## TDD Cycle

  1. Write unit tests for `handleEdit` and `handleDelete` (RED).
  2. Write structural tests for edit dialog and delete AlertDialog in the Vue file (RED).
  3. Implement edit/delete state, handlers, dialogs, and per-card buttons (GREEN).
  4. Run `cd src/dev-ui && npm run test` — all pass.
  5. Commit atomically.
---

## Spec Coverage

**Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

> GIVEN an authenticated user
> WHEN the user performs any create, read, update, or delete operation via the UI
> THEN the corresponding backend API call succeeds (2xx response)
> AND the UI reflects the updated state without requiring a manual refresh

## Gap

### Knowledge Graphs page is missing Update and Delete UI

**File:** `src/dev-ui/app/pages/knowledge-graphs/index.vue`

Each KG card renders two action buttons:

```vue
<div class="flex items-center gap-2">
  <Button size="sm" variant="outline" @click="navigateTo('/data-sources')">
    <Cable class="mr-1.5 size-3.5" />
    Add Data Source
  </Button>
  <Button size="sm" variant="outline" @click="navigateTo('/query')">
    <Database class="mr-1.5 size-3.5" />
    Query
  </Button>
</div>
```

There is no Edit or Delete button. The page has no `handleEdit`, `handleDelete`,
edit dialog, or delete confirmation dialog.

**Backend routes that exist but are not wired up:**

- `PATCH /management/knowledge-graphs/{kg_id}` — accepts `{ name: string, description: string }`,
  requires `edit` permission, returns `200` with the updated KG. Returns `409` on
  duplicate name, `404` if not found, `403` if no permission.

- `DELETE /management/knowledge-graphs/{kg_id}` — requires `manage` permission,
  returns `204 No Content`. Cascade-deletes all connected data sources.

**Consequence:** A user cannot rename a KG or remove one they no longer need. The
"update" and "delete" clauses of the Backend API Alignment spec scenario are
permanently failing because the UI provides no mechanism to perform them.

## Scope

### TDD — write tests first

Add to `src/dev-ui/app/tests/knowledge-graphs.test.ts`:

**Edit — logic tests:**

```typescript
describe('Knowledge Graphs — Edit (rename / re-describe)', () => {
  it('opens edit dialog pre-filled with existing name and description', () => {
    const editDialogOpen = { value: false }
    const editName = { value: '' }
    const editDescription = { value: '' }
    const editingKgId = { value: '' }

    function openEditDialog(kg: { id: string; name: string; description?: string }) {
      editingKgId.value = kg.id
      editName.value = kg.name
      editDescription.value = kg.description ?? ''
      editDialogOpen.value = true
    }

    openEditDialog({ id: 'kg-1', name: 'Engineering', description: 'Our main graph' })

    expect(editDialogOpen.value).toBe(true)
    expect(editingKgId.value).toBe('kg-1')
    expect(editName.value).toBe('Engineering')
    expect(editDescription.value).toBe('Our main graph')
  })

  it('calls PATCH /management/knowledge-graphs/{id} with name and description', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-1', name: 'Renamed Graph' })
    const editingKgId = { value: 'kg-1' }
    const editName = { value: 'Renamed Graph' }
    const editDescription = { value: 'Updated desc' }
    const saving = { value: false }
    const editDialogOpen = { value: true }
    const loadKnowledgeGraphs = vi.fn().mockResolvedValue(undefined)

    async function handleEdit() {
      if (!editName.value.trim()) return
      saving.value = true
      try {
        await apiFetch(`/management/knowledge-graphs/${editingKgId.value}`, {
          method: 'PATCH',
          body: { name: editName.value.trim(), description: editDescription.value.trim() },
        })
        editDialogOpen.value = false
        await loadKnowledgeGraphs()
      } finally {
        saving.value = false
      }
    }

    await handleEdit()

    expect(apiFetch).toHaveBeenCalledWith('/management/knowledge-graphs/kg-1', {
      method: 'PATCH',
      body: { name: 'Renamed Graph', description: 'Updated desc' },
    })
    expect(loadKnowledgeGraphs).toHaveBeenCalledOnce()
    expect(editDialogOpen.value).toBe(false)
    expect(saving.value).toBe(false)
  })

  it('shows inline error and does not call API when edit name is empty', async () => {
    const apiFetch = vi.fn()
    const editName = { value: '   ' }
    const editNameError = { value: '' }
    let apiCalled = false

    async function handleEdit() {
      editNameError.value = ''
      if (!editName.value.trim()) {
        editNameError.value = 'Knowledge graph name is required'
        return
      }
      apiCalled = true
      await apiFetch('/management/knowledge-graphs/kg-1', { method: 'PATCH', body: {} })
    }

    await handleEdit()

    expect(apiCalled).toBe(false)
    expect(editNameError.value).toBe('Knowledge graph name is required')
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('shows error toast and keeps dialog open on 409 conflict', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Name already exists in tenant'))
    const editingKgId = { value: 'kg-1' }
    const editName = { value: 'Duplicate Name' }
    const editDescription = { value: '' }
    const editDialogOpen = { value: true }
    const saving = { value: false }
    let errorMsg = ''

    async function handleEdit() {
      saving.value = true
      try {
        await apiFetch(`/management/knowledge-graphs/${editingKgId.value}`, {
          method: 'PATCH',
          body: { name: editName.value.trim(), description: editDescription.value.trim() },
        })
        editDialogOpen.value = false
      } catch (err) {
        errorMsg = err instanceof Error ? err.message : 'Failed to update knowledge graph'
        // dialog stays open
      } finally {
        saving.value = false
      }
    }

    await handleEdit()

    expect(errorMsg).toBe('Name already exists in tenant')
    expect(editDialogOpen.value).toBe(true) // still open
    expect(saving.value).toBe(false)
  })

  it('does not refresh list when edit API throws', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Forbidden'))
    const loadKnowledgeGraphs = vi.fn()
    const editName = { value: 'New Name' }

    async function handleEdit() {
      try {
        await apiFetch('/management/knowledge-graphs/kg-1', { method: 'PATCH', body: { name: editName.value } })
        await loadKnowledgeGraphs()
      } catch {
        // error path
      }
    }

    await handleEdit()
    expect(loadKnowledgeGraphs).not.toHaveBeenCalled()
  })
})
```

**Delete — logic tests:**

```typescript
describe('Knowledge Graphs — Delete with confirmation', () => {
  it('opens delete confirmation dialog with the target KG id', () => {
    const deleteDialogOpen = { value: false }
    const deletingKgId = { value: '' }
    const deletingKgName = { value: '' }

    function openDeleteDialog(kg: { id: string; name: string }) {
      deletingKgId.value = kg.id
      deletingKgName.value = kg.name
      deleteDialogOpen.value = true
    }

    openDeleteDialog({ id: 'kg-1', name: 'Engineering' })

    expect(deleteDialogOpen.value).toBe(true)
    expect(deletingKgId.value).toBe('kg-1')
    expect(deletingKgName.value).toBe('Engineering')
  })

  it('calls DELETE /management/knowledge-graphs/{id} and refreshes list on confirm', async () => {
    const apiFetch = vi.fn().mockResolvedValue(undefined) // 204 no content
    const deletingKgId = { value: 'kg-1' }
    const deleting = { value: false }
    const deleteDialogOpen = { value: true }
    const loadKnowledgeGraphs = vi.fn().mockResolvedValue(undefined)

    async function handleDelete() {
      deleting.value = true
      try {
        await apiFetch(`/management/knowledge-graphs/${deletingKgId.value}`, { method: 'DELETE' })
        deleteDialogOpen.value = false
        await loadKnowledgeGraphs()
      } finally {
        deleting.value = false
      }
    }

    await handleDelete()

    expect(apiFetch).toHaveBeenCalledWith('/management/knowledge-graphs/kg-1', { method: 'DELETE' })
    expect(loadKnowledgeGraphs).toHaveBeenCalledOnce()
    expect(deleteDialogOpen.value).toBe(false)
    expect(deleting.value).toBe(false)
  })

  it('does not call DELETE when dialog is cancelled', () => {
    const apiFetch = vi.fn()
    const deleteDialogOpen = { value: true }

    function cancelDelete() {
      deleteDialogOpen.value = false
      // no API call
    }

    cancelDelete()

    expect(apiFetch).not.toHaveBeenCalled()
    expect(deleteDialogOpen.value).toBe(false)
  })

  it('shows error toast and closes dialog on delete failure', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Forbidden'))
    const deleting = { value: false }
    const deleteDialogOpen = { value: true }
    let errorMsg = ''

    async function handleDelete() {
      deleting.value = true
      try {
        await apiFetch('/management/knowledge-graphs/kg-1', { method: 'DELETE' })
        deleteDialogOpen.value = false
      } catch (err) {
        errorMsg = err instanceof Error ? err.message : 'Failed to delete knowledge graph'
        deleteDialogOpen.value = false
      } finally {
        deleting.value = false
      }
    }

    await handleDelete()

    expect(errorMsg).toBe('Forbidden')
    expect(deleting.value).toBe(false)
    expect(deleteDialogOpen.value).toBe(false)
  })

  it('does not refresh list when delete API throws', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Server error'))
    const loadKnowledgeGraphs = vi.fn()

    async function handleDelete() {
      try {
        await apiFetch('/management/knowledge-graphs/kg-1', { method: 'DELETE' })
        await loadKnowledgeGraphs()
      } catch {
        // error path
      }
    }

    await handleDelete()
    expect(loadKnowledgeGraphs).not.toHaveBeenCalled()
  })
})
```

**Structural tests (verify template):**

```typescript
describe('Knowledge Graphs page — edit and delete structural checks', () => {
  const kgVue = readFileSync(
    resolve(__dirname, '../pages/knowledge-graphs/index.vue'),
    'utf-8',
  )

  it('declares editDialogOpen state', () => {
    expect(kgVue).toMatch(/editDialogOpen/)
  })

  it('declares deleteDialogOpen state', () => {
    expect(kgVue).toMatch(/deleteDialogOpen/)
  })

  it('calls PATCH /management/knowledge-graphs/ in handleEdit', () => {
    expect(kgVue).toMatch(/PATCH.*knowledge-graphs|knowledge-graphs.*PATCH/)
  })

  it('calls DELETE /management/knowledge-graphs/ in handleDelete', () => {
    expect(kgVue).toMatch(/DELETE.*knowledge-graphs|knowledge-graphs.*DELETE/)
  })

  it('edit dialog is present in the template', () => {
    expect(kgVue).toMatch(/editDialogOpen|Edit Knowledge Graph/)
  })

  it('delete AlertDialog is present in the template', () => {
    expect(kgVue).toMatch(/AlertDialog|deleteDialogOpen/)
  })

  it('cascade deletion warning mentions data sources', () => {
    expect(kgVue).toMatch(/data sources?/i)
  })

  it('handleEdit calls loadKnowledgeGraphs after success', () => {
    expect(kgVue).toContain('handleEdit')
    expect(kgVue).toContain('loadKnowledgeGraphs')
  })

  it('handleDelete calls loadKnowledgeGraphs after success', () => {
    expect(kgVue).toContain('handleDelete')
  })
})
```

### Implementation

#### 1. New imports in `<script setup>`

Add to the import block:

```typescript
import { Pencil, Trash2 } from 'lucide-vue-next'
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
```

#### 2. New state variables

```typescript
// Edit dialog
const editDialogOpen = ref(false)
const editingKgId = ref('')
const editName = ref('')
const editDescription = ref('')
const editNameError = ref('')
const saving = ref(false)

// Delete dialog
const deleteDialogOpen = ref(false)
const deletingKgId = ref('')
const deletingKgName = ref('')
const deleting = ref(false)
```

#### 3. `openEditDialog` + `handleEdit`

```typescript
function openEditDialog(kg: KnowledgeGraphItem) {
  editingKgId.value = kg.id
  editName.value = kg.name
  editDescription.value = kg.description ?? ''
  editNameError.value = ''
  editDialogOpen.value = true
}

async function handleEdit() {
  editNameError.value = ''
  if (!editName.value.trim()) {
    editNameError.value = 'Knowledge graph name is required'
    return
  }
  saving.value = true
  try {
    const { apiFetch } = useApiClient()
    await apiFetch(`/management/knowledge-graphs/${editingKgId.value}`, {
      method: 'PATCH',
      body: {
        name: editName.value.trim(),
        description: editDescription.value.trim(),
      },
    })
    toast.success('Knowledge graph updated')
    editDialogOpen.value = false
    await loadKnowledgeGraphs()
  } catch (err) {
    toast.error('Failed to update knowledge graph', {
      description: extractErrorMessage(err),
    })
  } finally {
    saving.value = false
  }
}
```

#### 4. `openDeleteDialog` + `handleDelete`

```typescript
function openDeleteDialog(kg: KnowledgeGraphItem) {
  deletingKgId.value = kg.id
  deletingKgName.value = kg.name
  deleteDialogOpen.value = true
}

async function handleDelete() {
  deleting.value = true
  try {
    const { apiFetch } = useApiClient()
    await apiFetch(`/management/knowledge-graphs/${deletingKgId.value}`, {
      method: 'DELETE',
    })
    toast.success(`Knowledge graph "${deletingKgName.value}" deleted`)
    deleteDialogOpen.value = false
    await loadKnowledgeGraphs()
  } catch (err) {
    toast.error('Failed to delete knowledge graph', {
      description: extractErrorMessage(err),
    })
    deleteDialogOpen.value = false
  } finally {
    deleting.value = false
  }
}
```

#### 5. Per-card action buttons (in the KG list template)

Add Edit and Delete buttons to the existing action group on each KG card:

```vue
<div class="flex items-center gap-2">
  <Button size="sm" variant="outline" @click="navigateTo('/data-sources')">
    <Cable class="mr-1.5 size-3.5" />
    Add Data Source
  </Button>
  <Button size="sm" variant="outline" @click="navigateTo('/query')">
    <Database class="mr-1.5 size-3.5" />
    Query
  </Button>
  <Button size="sm" variant="outline" @click="openEditDialog(kg)">
    <Pencil class="mr-1.5 size-3.5" />
    Edit
  </Button>
  <Button size="sm" variant="outline" class="text-destructive hover:bg-destructive/10" @click="openDeleteDialog(kg)">
    <Trash2 class="mr-1.5 size-3.5" />
    Delete
  </Button>
</div>
```

#### 6. Edit dialog (after the existing Create dialog)

```vue
<!-- Edit Knowledge Graph Dialog -->
<Dialog v-model:open="editDialogOpen">
  <DialogContent class="sm:max-w-md">
    <DialogHeader>
      <DialogTitle>Edit Knowledge Graph</DialogTitle>
      <DialogDescription>
        Update the name or description of this knowledge graph.
      </DialogDescription>
    </DialogHeader>
    <form class="space-y-4" @submit.prevent="handleEdit">
      <div class="space-y-1.5">
        <Label for="edit-kg-name">Name <span class="text-destructive">*</span></Label>
        <Input
          id="edit-kg-name"
          v-model="editName"
          placeholder="e.g. Engineering Knowledge Base"
          :disabled="saving"
          @input="editNameError = ''"
        />
        <p v-if="editNameError" class="text-sm text-destructive">{{ editNameError }}</p>
      </div>
      <div class="space-y-1.5">
        <Label for="edit-kg-description">Description</Label>
        <Input
          id="edit-kg-description"
          v-model="editDescription"
          placeholder="What does this knowledge graph represent?"
          :disabled="saving"
        />
      </div>
      <DialogFooter>
        <DialogClose as-child>
          <Button type="button" variant="outline" :disabled="saving">Cancel</Button>
        </DialogClose>
        <Button type="submit" :disabled="saving || !editName.trim()">
          <Loader2 v-if="saving" class="mr-2 size-4 animate-spin" />
          {{ saving ? 'Saving...' : 'Save' }}
        </Button>
      </DialogFooter>
    </form>
  </DialogContent>
</Dialog>
```

#### 7. Delete AlertDialog

```vue
<!-- Delete Knowledge Graph AlertDialog -->
<AlertDialog v-model:open="deleteDialogOpen">
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Delete "{{ deletingKgName }}"?</AlertDialogTitle>
      <AlertDialogDescription>
        This will permanently delete the knowledge graph and all of its data sources.
        This action cannot be undone.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel :disabled="deleting">Cancel</AlertDialogCancel>
      <AlertDialogAction
        class="bg-destructive text-destructive-foreground hover:bg-destructive/90"
        :disabled="deleting"
        @click.prevent="handleDelete"
      >
        <Loader2 v-if="deleting" class="mr-2 size-4 animate-spin" />
        {{ deleting ? 'Deleting...' : 'Delete' }}
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

## Acceptance Criteria

- `PATCH /management/knowledge-graphs/{id}` is called with `{ name, description }` when
  user saves an edit. On 200, the list refreshes and shows the new name.
- `DELETE /management/knowledge-graphs/{id}` is called when user confirms deletion.
  On 204, the KG disappears from the list.
- Edit dialog pre-fills the current name and description.
- Empty name in edit dialog shows inline error; API is not called.
- Duplicate name returns 409 and an error toast; edit dialog stays open.
- Delete dialog shows a warning that data sources will also be deleted.
- Cancelling the delete dialog makes no API call.
- Success toasts appear for both edit and delete operations.
- Error toasts appear for both operations on API failure.
- Both `saving` and `deleting` flags are reset to `false` in all code paths (finally block).
- All new unit tests and structural tests pass (`cd src/dev-ui && npm run test`).
- No regressions on the existing Knowledge Graphs page tests.

## TDD Cycle

1. Write unit tests for `handleEdit` (validation, API call, refresh, error) — RED.
2. Write unit tests for `handleDelete` (confirm, cancel, refresh, error) — RED.
3. Write structural tests for edit/delete presence in the Vue file — RED.
4. Implement `openEditDialog`, `handleEdit`, `openDeleteDialog`, `handleDelete` and
   the two dialog templates in `knowledge-graphs/index.vue` — GREEN.
5. Run `cd src/dev-ui && npm run test` — all pass.
6. Commit atomically.
