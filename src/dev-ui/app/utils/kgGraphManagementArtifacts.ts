import { cn } from '@/lib/utils'
import {
  filterRailItemsForMode,
  type GraphManagementMode,
  type GraphManagementRailItem,
  type GraphManagementRailItemId,
} from './kgGraphManagement'
import type { StepStatusLabel } from './kgManageWorkspace'

export function filterSchemaRailItems(items: GraphManagementRailItem[]): GraphManagementRailItem[] {
  return items.filter((item) => item.id !== 'session-pointers')
}

export function resolveSchemaRailSelection(
  selectedId: GraphManagementRailItemId | null,
  mode: GraphManagementMode,
  items: GraphManagementRailItem[],
): GraphManagementRailItemId | null {
  const schemaItems = filterSchemaRailItems(filterRailItemsForMode(items, mode))
  if (schemaItems.length === 0) return null
  if (selectedId && schemaItems.some((item) => item.id === selectedId)) {
    return selectedId
  }
  return schemaItems[0]?.id ?? null
}

export function graphManagementRailItemDone(status: StepStatusLabel): boolean {
  return status === 'ready'
}

export function graphManagementArtifactRowClass(selected: boolean, done: boolean): string {
  return cn(
    'flex w-full flex-col gap-0.5 rounded-lg border p-2.5 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
    done
      ? 'border-green-500/35 bg-green-500/5 dark:border-green-500/25 dark:bg-green-950/15'
      : 'border-border bg-card hover:bg-muted/50',
    selected && 'ring-2 ring-primary/30',
  )
}

export function graphManagementArtifactHint(item: GraphManagementRailItem): string {
  if (item.id === 'schema-entities') {
    return item.status === 'ready' ? 'Types available' : 'Define entities'
  }
  if (item.id === 'schema-relationships') {
    return item.status === 'ready' ? 'Types available' : 'Define relationships'
  }
  if (item.id === 'schema-readiness') {
    return item.status === 'ready' ? 'Ready to transition' : 'Bootstrap checklist'
  }
  if (item.id === 'validation-diagnostics') {
    return item.status === 'ready' ? 'No blocking issues' : 'Review diagnostics'
  }
  if (item.id === 'extraction-jobs-setup') {
    return item.status === 'ready' ? 'Operations mode' : 'Complete schema first'
  }
  if (item.id === 'mutation-authoring') {
    return item.status === 'ready' ? 'JSONL mutations' : 'Complete schema first'
  }
  return item.detailHint
}
