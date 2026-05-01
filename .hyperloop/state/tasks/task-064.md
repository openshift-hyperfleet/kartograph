---
id: task-064
title: Data sources — animated progress indicator for active sync phases
spec_ref: "specs/ui/experience.spec.md@14b2efabc5d0910e59494fd9b111b00c8a4383b3"
status: not-started
phase: null
deps:
  - task-041
  - task-042
round: 0
branch: null
pr: null
pr_title: "feat(ui): add animated phase progress indicator for active data source sync runs"
pr_description: |
  ## What & Why

  The Sync Monitoring spec requires "a progress indicator **appropriate to the current
  phase**" when a data source sync is in progress. The existing implementation shows a
  static status Badge (e.g., `Ingesting`, `Extracting`) but provides no animated or
  visual progress cue to communicate that work is actively happening.

  Without an animated indicator, a user watching a long sync run cannot distinguish
  "the sync is paused / stuck" from "the sync is actively running" — both show the same
  static badge. An animated spinner or pulsing indicator gives immediate visual
  confirmation that the system is working.

  ## Spec Requirements Satisfied

  **Requirement: Sync Monitoring — Scenario: Active sync progress**
  > GIVEN a data source with a sync in progress
  > WHEN the user views the data source
  > THEN they see the current sync status (ingesting, extracting, applying)
  > AND **a progress indicator appropriate to the current phase**

  The "a progress indicator appropriate to the current phase" requirement is not satisfied
  by a static badge alone. Each active phase should have a distinct visual treatment.

  ## Key Design Decisions

  - **Phase-appropriate indicators:**
    - `pending` — subtle pulsing dot (waiting for a worker)
    - `ingesting` — spinner with a network/download icon (reading from external source)
    - `ai_extracting` — spinner with a sparkles/brain icon (AI processing)
    - `applying` — progress pulse with a database icon (writing to graph)
  - Indicators appear **inline** on the sync run row in the history list, replacing (or
    augmenting) the status badge for active phases. Completed and failed runs keep the
    existing badge-only display.
  - The Kartograph design language is used throughout: Lucide icons, Tailwind `animate-spin`
    / `animate-pulse`, OKLCH primary color tokens.
  - A `SyncPhaseIndicator.vue` component encapsulates the logic so it can be reused if
    sync status appears elsewhere (e.g., the data source card header badge in the nav layout).

  ## Files Affected

  - `src/dev-ui/app/components/graph/SyncPhaseIndicator.vue` — new component (TDD-first).
    Props: `status: SyncRun['status']`. Renders the appropriate animated indicator.
  - `src/dev-ui/app/pages/data-sources/index.vue` — replace the inline Badge in the sync
    history rows with `<SyncPhaseIndicator :status="run.status" />` for active phases;
    keep the static Badge for completed/failed.
  - `src/dev-ui/app/tests/sync-phase-indicator.test.ts` — new test file (TDD-first).

  ## How to Verify

  1. Navigate to Data Sources with at least one data source that has an active sync run
     (status `ingesting`, `ai_extracting`, or `applying`).
  2. The sync run row shows an animated spinner (or phase-appropriate animation) next to
     the phase label.
  3. A completed run shows only the static Badge, no spinner.
  4. A failed run shows only the destructive Badge, no spinner.
  5. Run `cd src/dev-ui && pnpm test` — all tests in `sync-phase-indicator.test.ts` pass.
  6. Run tests from `sync-monitoring-extended.test.ts` — no regressions.

  ## Caveats

  - Depends on task-041 (fixes data source API response format) so sync runs are populated
    correctly, and task-042 (fixes status type values) so the status strings match.
  - The indicator is purely visual — no polling is added by this task. Polling (for
    real-time status updates) is a separate concern and a potential future task.
  - The `SyncPhaseIndicator` component must handle the `undefined`/`null` run case
    gracefully (data source with no sync runs yet shows nothing).
---

## Spec Coverage

**Requirement: Sync Monitoring — Scenario: Active sync progress** from
`specs/ui/experience.spec.md`:

> GIVEN a data source with a sync in progress
> WHEN the user views the data source
> THEN they see the current sync status (ingesting, extracting, applying)
> AND **a progress indicator appropriate to the current phase**

## Gap

`src/dev-ui/app/pages/data-sources/index.vue` renders sync run history as:

```html
<Badge :variant="run.status === 'completed' ? 'default' : run.status === 'failed' ? 'destructive' : 'secondary'">
  {{ syncPhaseLabel(run.status) }}
</Badge>
```

And the data source card header badge:

```html
<Badge :variant="ds.sync_runs?.[0]?.status === 'completed' ? 'default' : ...">
  {{ ds.sync_runs?.[0] ? syncPhaseLabel(ds.sync_runs[0].status) : 'Idle' }}
</Badge>
```

Both show a **static Badge** with a text label. For completed (`Completed`) and failed
(`Failed`) runs this is appropriate. For active phases (`pending`, `ingesting`,
`ai_extracting`, `applying`), the spec requires "a progress indicator appropriate to the
current phase" — an animated element that communicates liveness.

No existing task covers this visual gap:
- task-042 (not-started, old SHA) fixes the phase status type values (string mismatch between backend and UI)
- task-041 (not-started, old SHA) fixes the API response format
- task-047 (not-started, old SHA) adds the nav-bar sync badge

None of these add an animated progress indicator on the data source card or sync history row.

## Scope

### TDD — write tests first

Create `src/dev-ui/app/tests/sync-phase-indicator.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'

type SyncStatus = 'pending' | 'ingesting' | 'ai_extracting' | 'applying' | 'completed' | 'failed'

/**
 * Core logic: determine whether a given status warrants an animated indicator
 * vs. a static badge.
 */
function isAnimatedStatus(status: SyncStatus): boolean {
  return status === 'pending' || status === 'ingesting' || status === 'ai_extracting' || status === 'applying'
}

/**
 * Determine the indicator style for a given active phase.
 */
type IndicatorStyle = 'pulse' | 'spin'

function getIndicatorStyle(status: SyncStatus): IndicatorStyle | null {
  switch (status) {
    case 'pending':    return 'pulse'
    case 'ingesting':  return 'spin'
    case 'ai_extracting': return 'spin'
    case 'applying':   return 'pulse'
    default:           return null
  }
}

describe('SyncPhaseIndicator — isAnimatedStatus()', () => {
  it('returns true for pending', () => {
    expect(isAnimatedStatus('pending')).toBe(true)
  })
  it('returns true for ingesting', () => {
    expect(isAnimatedStatus('ingesting')).toBe(true)
  })
  it('returns true for ai_extracting', () => {
    expect(isAnimatedStatus('ai_extracting')).toBe(true)
  })
  it('returns true for applying', () => {
    expect(isAnimatedStatus('applying')).toBe(true)
  })
  it('returns false for completed', () => {
    expect(isAnimatedStatus('completed')).toBe(false)
  })
  it('returns false for failed', () => {
    expect(isAnimatedStatus('failed')).toBe(false)
  })
})

describe('SyncPhaseIndicator — getIndicatorStyle()', () => {
  it('pending uses pulse (waiting)', () => {
    expect(getIndicatorStyle('pending')).toBe('pulse')
  })
  it('ingesting uses spin (actively reading)', () => {
    expect(getIndicatorStyle('ingesting')).toBe('spin')
  })
  it('ai_extracting uses spin (AI processing)', () => {
    expect(getIndicatorStyle('ai_extracting')).toBe('spin')
  })
  it('applying uses pulse (writing)', () => {
    expect(getIndicatorStyle('applying')).toBe('pulse')
  })
  it('completed returns null (no animation needed)', () => {
    expect(getIndicatorStyle('completed')).toBeNull()
  })
  it('failed returns null (no animation needed)', () => {
    expect(getIndicatorStyle('failed')).toBeNull()
  })
})
```

### Implementation

#### 1. Create `SyncPhaseIndicator.vue`

**Location:** `src/dev-ui/app/components/graph/SyncPhaseIndicator.vue`

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { Loader2, Download, Sparkles, Database, Clock } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'

type SyncStatus = 'pending' | 'ingesting' | 'ai_extracting' | 'applying' | 'completed' | 'failed'

const props = defineProps<{ status: SyncStatus; label?: string }>()

const phaseLabel = computed(() => {
  const labels: Record<SyncStatus, string> = {
    pending:       'Pending',
    ingesting:     'Ingesting',
    ai_extracting: 'Extracting',
    applying:      'Applying',
    completed:     'Completed',
    failed:        'Failed',
  }
  return props.label ?? labels[props.status] ?? props.status
})

const isActive = computed(() =>
  ['pending', 'ingesting', 'ai_extracting', 'applying'].includes(props.status),
)

const badgeVariant = computed(() => {
  if (props.status === 'completed') return 'default'
  if (props.status === 'failed') return 'destructive'
  return 'secondary'
})

const phaseIcon = computed(() => {
  switch (props.status) {
    case 'pending':       return Clock
    case 'ingesting':     return Download
    case 'ai_extracting': return Sparkles
    case 'applying':      return Database
    default:              return null
  }
})

const animationClass = computed(() => {
  switch (props.status) {
    case 'ingesting':
    case 'ai_extracting': return 'animate-spin'
    case 'pending':
    case 'applying':      return 'animate-pulse'
    default:              return ''
  }
})
</script>

<template>
  <span class="inline-flex items-center gap-1.5">
    <!-- Animated icon for active phases -->
    <component
      :is="phaseIcon"
      v-if="isActive && phaseIcon"
      class="size-3.5 text-primary"
      :class="animationClass"
      aria-hidden="true"
    />
    <Badge :variant="badgeVariant" class="text-[10px]">
      {{ phaseLabel }}
    </Badge>
  </span>
</template>
```

#### 2. Update `data-sources/index.vue` — sync history rows

Replace the inline Badge in the sync history list with:

```html
<SyncPhaseIndicator :status="run.status" />
```

#### 3. Update `data-sources/index.vue` — data source card header badge

Replace the inline Badge in the card header with:

```html
<SyncPhaseIndicator
  v-if="ds.sync_runs?.[0]"
  :status="ds.sync_runs[0].status"
/>
<Badge v-else variant="secondary" class="text-[10px]">Idle</Badge>
```

#### 4. Import the component

```typescript
import SyncPhaseIndicator from '@/components/graph/SyncPhaseIndicator.vue'
```

## Acceptance Criteria

- Active sync phases (`pending`, `ingesting`, `ai_extracting`, `applying`) show an animated
  Lucide icon (spinning for ingesting/extracting, pulsing for pending/applying) alongside
  the phase label in the sync history row and the data source card header.
- Completed and failed runs show only the static Badge (no icon, no animation).
- Data sources with no sync runs show "Idle" (no animated component rendered).
- All tests in `src/dev-ui/app/tests/sync-phase-indicator.test.ts` pass.
- No regressions: `cd src/dev-ui && pnpm test` (including `sync-monitoring-extended.test.ts`).

## TDD Cycle

1. Create `src/dev-ui/app/tests/sync-phase-indicator.test.ts` with the tests above (RED for any failing utilities).
2. Create `src/dev-ui/app/components/graph/SyncPhaseIndicator.vue` with the logic.
3. Wire `SyncPhaseIndicator` into `data-sources/index.vue`.
4. Run `cd src/dev-ui && pnpm test` (GREEN).
5. Commit atomically.
