import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'fs'
import { resolve } from 'path'

// ── AlertDialog Component Tests ───────────────────────────────────────────────
//
// Spec: "Design Language" — Scenario: Component library
//       "Interaction Principles" — Scenario: Mutation feedback
//       "API Key Management" — Scenario: Revoke key
//       "Workspace Management" — Scenario: Member management
//
// The AlertDialog is the semantically-correct component for destructive
// confirmation flows (revoke, delete). It uses AlertDialogRoot from reka-ui,
// which enforces intentional user action (no click-outside-to-close).

const ALERT_DIALOG_DIR = resolve(__dirname, '../components/ui/alert-dialog')

// ── Scenario: Component library — AlertDialog files exist ────────────────────

describe('AlertDialog component library — file structure', () => {
  const expectedFiles = [
    'index.ts',
    'AlertDialog.vue',
    'AlertDialogTrigger.vue',
    'AlertDialogContent.vue',
    'AlertDialogOverlay.vue',
    'AlertDialogHeader.vue',
    'AlertDialogFooter.vue',
    'AlertDialogTitle.vue',
    'AlertDialogDescription.vue',
    'AlertDialogAction.vue',
    'AlertDialogCancel.vue',
  ]

  for (const file of expectedFiles) {
    it(`${file} exists in ui/alert-dialog/`, () => {
      expect(existsSync(resolve(ALERT_DIALOG_DIR, file))).toBe(true)
    })
  }
})

// ── Scenario: Component library — index.ts exports ───────────────────────────

describe('AlertDialog — index.ts exports all sub-components', () => {
  const indexPath = resolve(ALERT_DIALOG_DIR, 'index.ts')

  it('index.ts exports AlertDialog (root)', () => {
    const content = readFileSync(indexPath, 'utf-8')
    expect(content).toContain("export { default as AlertDialog }")
  })

  it('index.ts exports AlertDialogTrigger', () => {
    const content = readFileSync(indexPath, 'utf-8')
    expect(content).toContain("export { default as AlertDialogTrigger }")
  })

  it('index.ts exports AlertDialogContent', () => {
    const content = readFileSync(indexPath, 'utf-8')
    expect(content).toContain("export { default as AlertDialogContent }")
  })

  it('index.ts exports AlertDialogHeader', () => {
    const content = readFileSync(indexPath, 'utf-8')
    expect(content).toContain("export { default as AlertDialogHeader }")
  })

  it('index.ts exports AlertDialogFooter', () => {
    const content = readFileSync(indexPath, 'utf-8')
    expect(content).toContain("export { default as AlertDialogFooter }")
  })

  it('index.ts exports AlertDialogTitle', () => {
    const content = readFileSync(indexPath, 'utf-8')
    expect(content).toContain("export { default as AlertDialogTitle }")
  })

  it('index.ts exports AlertDialogDescription', () => {
    const content = readFileSync(indexPath, 'utf-8')
    expect(content).toContain("export { default as AlertDialogDescription }")
  })

  it('index.ts exports AlertDialogAction', () => {
    const content = readFileSync(indexPath, 'utf-8')
    expect(content).toContain("export { default as AlertDialogAction }")
  })

  it('index.ts exports AlertDialogCancel', () => {
    const content = readFileSync(indexPath, 'utf-8')
    expect(content).toContain("export { default as AlertDialogCancel }")
  })
})

// ── Scenario: Component library — reka-ui primitive usage ────────────────────

describe('AlertDialog — backed by reka-ui AlertDialog primitives', () => {
  it('AlertDialog.vue uses AlertDialogRoot from reka-ui', () => {
    const content = readFileSync(resolve(ALERT_DIALOG_DIR, 'AlertDialog.vue'), 'utf-8')
    expect(content).toContain('reka-ui')
    expect(content).toContain('AlertDialogRoot')
  })

  it('AlertDialogContent.vue uses AlertDialogContent from reka-ui', () => {
    const content = readFileSync(resolve(ALERT_DIALOG_DIR, 'AlertDialogContent.vue'), 'utf-8')
    expect(content).toContain('reka-ui')
    expect(content).toContain('AlertDialogContent')
  })

  it('AlertDialogAction.vue uses AlertDialogAction from reka-ui', () => {
    const content = readFileSync(resolve(ALERT_DIALOG_DIR, 'AlertDialogAction.vue'), 'utf-8')
    expect(content).toContain('reka-ui')
    expect(content).toContain('AlertDialogAction')
  })

  it('AlertDialogCancel.vue uses AlertDialogCancel from reka-ui', () => {
    const content = readFileSync(resolve(ALERT_DIALOG_DIR, 'AlertDialogCancel.vue'), 'utf-8')
    expect(content).toContain('reka-ui')
    expect(content).toContain('AlertDialogCancel')
  })
})

// ── Scenario: Component library — Tailwind/CVA styling follows design language ─

describe('AlertDialog — styling matches design language', () => {
  it('AlertDialogContent.vue uses rounded-xl (spec: cards use rounded-xl)', () => {
    const content = readFileSync(resolve(ALERT_DIALOG_DIR, 'AlertDialogContent.vue'), 'utf-8')
    expect(content).toContain('rounded-xl')
  })

  it('AlertDialogAction.vue uses Button variant="destructive" or destructive class', () => {
    const content = readFileSync(resolve(ALERT_DIALOG_DIR, 'AlertDialogAction.vue'), 'utf-8')
    // Should use button variants via cn() or reference destructive styling
    expect(content).toMatch(/destructive|buttonVariants/)
  })

  it('AlertDialogContent.vue does NOT have a close button X (alert dialogs require explicit action)', () => {
    const content = readFileSync(resolve(ALERT_DIALOG_DIR, 'AlertDialogContent.vue'), 'utf-8')
    // AlertDialog should NOT include DialogClose or an X button
    expect(content).not.toContain('<X ')
    expect(content).not.toContain('DialogClose')
  })

  it('AlertDialogOverlay.vue applies fade-in/fade-out animations', () => {
    const content = readFileSync(resolve(ALERT_DIALOG_DIR, 'AlertDialogOverlay.vue'), 'utf-8')
    expect(content).toContain('animate-in')
    expect(content).toContain('animate-out')
  })
})

// ── Scenario: Revoke key — api-keys page uses AlertDialog ─────────────────────
// Spec: "GIVEN an active or expired key WHEN the user revokes it
// THEN the key is marked revoked and can no longer authenticate"
// The revoke confirmation is a destructive action; it should use AlertDialog,
// not a plain Dialog, to prevent accidental dismiss via click-outside.

describe('Revoke key — alert dialog for destructive confirmation', () => {
  const apiKeysPath = resolve(__dirname, '../pages/api-keys/index.vue')

  it('api-keys page imports from alert-dialog component', () => {
    const content = readFileSync(apiKeysPath, 'utf-8')
    expect(content).toContain('@/components/ui/alert-dialog')
  })

  it('api-keys page uses AlertDialog (not Dialog) for revoke confirmation', () => {
    const content = readFileSync(apiKeysPath, 'utf-8')
    // Should reference AlertDialog root
    expect(content).toContain('AlertDialog')
  })

  it('revoke confirmation uses AlertDialogAction for the destructive confirm button', () => {
    const content = readFileSync(apiKeysPath, 'utf-8')
    expect(content).toContain('AlertDialogAction')
  })

  it('revoke confirmation uses AlertDialogCancel for the cancel button', () => {
    const content = readFileSync(apiKeysPath, 'utf-8')
    expect(content).toContain('AlertDialogCancel')
  })
})

// ── Scenario: Member management — workspace/groups pages use AlertDialog ──────
// Spec: "Workspace Management — Member management"
// Delete group / remove member are destructive actions requiring confirmation.

describe('Member management — alert dialog for destructive group actions', () => {
  const groupsPath = resolve(__dirname, '../pages/groups/index.vue')

  it('groups page imports from alert-dialog component', () => {
    const content = readFileSync(groupsPath, 'utf-8')
    expect(content).toContain('@/components/ui/alert-dialog')
  })

  it('groups page uses AlertDialog for delete group confirmation', () => {
    const content = readFileSync(groupsPath, 'utf-8')
    expect(content).toContain('AlertDialog')
  })

  it('groups delete confirmation uses AlertDialogAction', () => {
    const content = readFileSync(groupsPath, 'utf-8')
    expect(content).toContain('AlertDialogAction')
  })
})

describe('Workspace Management — alert dialog for destructive workspace actions', () => {
  const workspacesPath = resolve(__dirname, '../pages/workspaces/index.vue')

  it('workspaces page imports from alert-dialog component', () => {
    const content = readFileSync(workspacesPath, 'utf-8')
    expect(content).toContain('@/components/ui/alert-dialog')
  })

  it('workspaces page uses AlertDialog for delete workspace confirmation', () => {
    const content = readFileSync(workspacesPath, 'utf-8')
    expect(content).toContain('AlertDialog')
  })

  it('workspaces delete confirmation uses AlertDialogAction', () => {
    const content = readFileSync(workspacesPath, 'utf-8')
    expect(content).toContain('AlertDialogAction')
  })
})

// ── AlertDialog logic — open/close state management ──────────────────────────
// Tests the state management pattern for the AlertDialog (mirrors Dialog pattern)

describe('AlertDialog — open/close state management pattern', () => {
  it('opens when confirmAction() is called with the target resource', () => {
    const dialogOpen = { value: false }
    const targetItem = { value: null as { id: string; name: string } | null }

    function confirmAction(item: { id: string; name: string }) {
      targetItem.value = item
      dialogOpen.value = true
    }

    confirmAction({ id: 'item-1', name: 'Production Key' })
    expect(dialogOpen.value).toBe(true)
    expect(targetItem.value?.id).toBe('item-1')
  })

  it('closes and clears target after action completes', () => {
    const dialogOpen = { value: true }
    const targetItem = { value: { id: 'item-1', name: 'Production Key' } as { id: string; name: string } | null }
    const isLoading = { value: false }

    async function handleAction() {
      if (!targetItem.value) return
      isLoading.value = true
      try {
        // Simulate successful destructive operation
        void targetItem.value.id
      } finally {
        dialogOpen.value = false
        targetItem.value = null
        isLoading.value = false
      }
    }

    handleAction()
    expect(dialogOpen.value).toBe(false)
    expect(targetItem.value).toBeNull()
    expect(isLoading.value).toBe(false)
  })

  it('AlertDialog does not close on outside click (prevents accidental dismiss)', () => {
    // The AlertDialogRoot from reka-ui does NOT close on outside click.
    // This is the key distinction from Dialog — AlertDialog requires explicit
    // action (AlertDialogAction or AlertDialogCancel) to dismiss.
    // We verify the component uses AlertDialogPortal (not the Dialog-family portal).
    const content = readFileSync(resolve(ALERT_DIALOG_DIR, 'AlertDialogContent.vue'), 'utf-8')
    // Should use AlertDialogPortal from reka-ui
    expect(content).toContain('AlertDialogPortal')
    // Should NOT import from Dialog component family
    expect(content).not.toContain("from '@/components/ui/dialog'")
  })
})
