<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  LayoutDashboard,
  Database,
  Share2,
  Terminal,
  KeyRound,
  Plug,
  FolderTree,
  Building2,
  ArrowRight,
  CheckCircle2,
  Circle,
  X,
  Loader2,
} from 'lucide-vue-next'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'

import type { SchemaLabelsResponse, APIKeyResponse, WorkspaceListResponse } from '~/types'

const { listNodeLabels, listEdgeLabels } = useGraphApi()
const { listApiKeys, listWorkspaces } = useIamApi()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, currentTenantName, tenantVersion } = useTenant()

// ── Stats state ──────────────────────────────────────────────────────────

const statsLoading = ref(false)
const nodeTypeCount = ref<number | null>(null)
const edgeTypeCount = ref<number | null>(null)
const apiKeyCount = ref<number | null>(null)
const workspaceCount = ref<number | null>(null)
const apiKeys = ref<APIKeyResponse[]>([])

// ── Onboarding state ─────────────────────────────────────────────────────

const ONBOARDING_KEY = 'kartograph:onboarding-dismissed'

const onboardingDismissed = ref(false)

function loadOnboardingState() {
  if (typeof window !== 'undefined') {
    onboardingDismissed.value = localStorage.getItem(ONBOARDING_KEY) === 'true'
  }
}

function dismissOnboarding() {
  onboardingDismissed.value = true
  if (typeof window !== 'undefined') {
    localStorage.setItem(ONBOARDING_KEY, 'true')
  }
}

// ── Checklist computed ───────────────────────────────────────────────────

const checklistItems = computed(() => [
  {
    done: hasTenant.value,
    label: 'Create a tenant',
    description: 'You need a tenant to organize your knowledge graphs.',
    actionTo: '/tenants',
    actionLabel: 'Manage Tenants',
  },
  {
    done: (nodeTypeCount.value ?? 0) > 0,
    label: 'Define a node type',
    description: 'Add at least one node type to your graph schema.',
    actionTo: '/graph/schema',
    actionLabel: 'Browse Schema',
  },
  {
    done: (apiKeyCount.value ?? 0) > 0,
    label: 'Create an API key',
    description: 'Generate an API key for programmatic access.',
    actionTo: '/api-keys',
    actionLabel: 'Create API Key',
  },
  {
    done: apiKeys.value.some((k) => k.last_used_at !== null),
    label: 'Connect via MCP',
    description: 'Use your API key to connect an AI agent via MCP.',
    actionTo: '/integrate/mcp',
    actionLabel: 'MCP Integration',
  },
])

const allChecklistDone = computed(() => checklistItems.value.every((item) => item.done))
const completedCount = computed(() => checklistItems.value.filter((item) => item.done).length)

const showChecklist = computed(() => {
  if (onboardingDismissed.value) return false
  return !allChecklistDone.value
})

// ── Stats cards config ───────────────────────────────────────────────────

const statsCards = computed(() => [
  {
    label: 'Node Types',
    count: nodeTypeCount.value,
    icon: Database,
    to: '/graph/schema',
  },
  {
    label: 'Edge Types',
    count: edgeTypeCount.value,
    icon: Share2,
    to: '/graph/schema',
  },
  {
    label: 'API Keys',
    count: apiKeyCount.value,
    icon: KeyRound,
    to: '/api-keys',
  },
  {
    label: 'Workspaces',
    count: workspaceCount.value,
    icon: FolderTree,
    to: '/workspaces',
  },
])

// ── Quick actions config ─────────────────────────────────────────────────

const quickActions = [
  {
    title: 'Browse Schema',
    description: 'Explore node and edge type definitions',
    icon: Database,
    to: '/graph/schema',
  },
  {
    title: 'Explore Graph',
    description: 'Visualize nodes and relationships',
    icon: Share2,
    to: '/graph/explorer',
  },
  {
    title: 'Run Query',
    description: 'Execute Cypher queries against the graph',
    icon: Terminal,
    to: '/query',
  },
  {
    title: 'Create API Key',
    description: 'Generate keys for programmatic access',
    icon: KeyRound,
    to: '/api-keys',
  },
  {
    title: 'MCP Integration',
    description: 'Connect AI agents via Model Context Protocol',
    icon: Plug,
    to: '/integrate/mcp',
  },
  {
    title: 'Manage Workspaces',
    description: 'Organize resources with workspaces',
    icon: FolderTree,
    to: '/workspaces',
  },
]

// ── Data fetching ────────────────────────────────────────────────────────

async function fetchStats() {
  if (!hasTenant.value) return
  statsLoading.value = true

  // Fetch all in parallel, each independently catching errors
  const [nodeResult, edgeResult, keysResult, wsResult] = await Promise.allSettled([
    listNodeLabels(),
    listEdgeLabels(),
    listApiKeys(),
    listWorkspaces(),
  ])

  nodeTypeCount.value = nodeResult.status === 'fulfilled'
    ? (nodeResult.value as SchemaLabelsResponse).count
    : null
  edgeTypeCount.value = edgeResult.status === 'fulfilled'
    ? (edgeResult.value as SchemaLabelsResponse).count
    : null

  if (keysResult.status === 'fulfilled') {
    const keys = keysResult.value as APIKeyResponse[]
    apiKeys.value = keys
    apiKeyCount.value = keys.filter((k) => !k.is_revoked).length
  } else {
    apiKeys.value = []
    apiKeyCount.value = null
  }

  workspaceCount.value = wsResult.status === 'fulfilled'
    ? (wsResult.value as WorkspaceListResponse).count
    : null

  statsLoading.value = false
}

onMounted(() => {
  loadOnboardingState()
  if (hasTenant.value) fetchStats()
})

watch(tenantVersion, () => {
  if (hasTenant.value) fetchStats()
})
</script>

<template>
  <div class="space-y-8">
    <!-- No tenant selected -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the sidebar to get started.</p>
    </div>

    <template v-else>
      <!-- A. Welcome Header -->
      <div>
        <div class="flex items-center gap-3">
          <LayoutDashboard class="size-6 text-muted-foreground" />
          <div>
            <h1 class="text-2xl font-bold tracking-tight">
              Welcome to Kartograph
            </h1>
            <p class="text-sm text-muted-foreground">
              Knowledge graph platform
              <span v-if="currentTenantName"> — {{ currentTenantName }}</span>
            </p>
          </div>
        </div>
      </div>

      <Separator />

      <!-- B. Quick Stats Cards -->
      <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
        <NuxtLink
          v-for="stat in statsCards"
          :key="stat.label"
          :to="stat.to"
          class="group"
        >
          <Card class="transition-colors group-hover:border-primary/30">
            <CardContent class="flex items-center gap-3 p-4">
              <div class="rounded-md bg-muted p-2">
                <component :is="stat.icon" class="size-4 text-muted-foreground" />
              </div>
              <div class="min-w-0">
                <div class="text-2xl font-bold tracking-tight">
                  <template v-if="statsLoading">
                    <Loader2 class="size-5 animate-spin text-muted-foreground" />
                  </template>
                  <template v-else>
                    {{ stat.count !== null ? stat.count : '—' }}
                  </template>
                </div>
                <p class="text-xs text-muted-foreground truncate">{{ stat.label }}</p>
              </div>
            </CardContent>
          </Card>
        </NuxtLink>
      </div>

      <!-- D. Getting Started Checklist (Token 7) -->
      <Card v-if="showChecklist">
        <CardHeader class="flex flex-row items-center justify-between space-y-0 pb-3">
          <div>
            <CardTitle class="text-base">Getting Started</CardTitle>
            <CardDescription>
              {{ completedCount }} of {{ checklistItems.length }} completed
            </CardDescription>
          </div>
          <Button variant="ghost" size="icon" class="size-8" @click="dismissOnboarding">
            <X class="size-4" />
          </Button>
        </CardHeader>
        <CardContent class="space-y-3">
          <!-- Progress bar -->
          <div class="h-1.5 w-full rounded-full bg-muted">
            <div
              class="h-1.5 rounded-full bg-primary transition-all"
              :style="{ width: `${(completedCount / checklistItems.length) * 100}%` }"
            />
          </div>

          <div class="space-y-2">
            <div
              v-for="item in checklistItems"
              :key="item.label"
              class="flex items-start gap-3 rounded-md p-2"
              :class="item.done ? 'opacity-60' : ''"
            >
              <CheckCircle2 v-if="item.done" class="mt-0.5 size-4 shrink-0 text-green-600" />
              <Circle v-else class="mt-0.5 size-4 shrink-0 text-muted-foreground" />
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium" :class="item.done ? 'line-through' : ''">
                  {{ item.label }}
                </p>
                <p class="text-xs text-muted-foreground">{{ item.description }}</p>
              </div>
              <NuxtLink v-if="!item.done" :to="item.actionTo">
                <Button variant="ghost" size="sm" class="h-7 text-xs">
                  {{ item.actionLabel }}
                  <ArrowRight class="ml-1 size-3" />
                </Button>
              </NuxtLink>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- C. Quick Actions Grid -->
      <div>
        <h2 class="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Quick Actions
        </h2>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <NuxtLink
            v-for="action in quickActions"
            :key="action.title"
            :to="action.to"
            class="group"
          >
            <Card class="h-full transition-colors group-hover:border-primary/30">
              <CardContent class="flex items-start gap-3 p-4">
                <div class="rounded-md bg-muted p-2">
                  <component :is="action.icon" class="size-4 text-muted-foreground" />
                </div>
                <div class="min-w-0">
                  <p class="text-sm font-medium group-hover:text-primary transition-colors">
                    {{ action.title }}
                  </p>
                  <p class="text-xs text-muted-foreground">{{ action.description }}</p>
                </div>
              </CardContent>
            </Card>
          </NuxtLink>
        </div>
      </div>
    </template>
  </div>
</template>
