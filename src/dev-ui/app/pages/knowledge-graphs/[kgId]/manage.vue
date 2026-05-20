<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { ArrowLeft, CheckCircle2, Loader2, PlayCircle, ShieldAlert } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'

interface WorkspaceReadinessStatus {
  has_minimum_entity_types: boolean
  has_minimum_relationship_types: boolean
  prepopulated_types_ready: boolean
  prepopulated_types_without_instances: string[]
  blocking_reasons: string[]
}

interface WorkspaceSessionPointers {
  active_schema_bootstrap_session_id: string | null
  active_extraction_operations_session_id: string | null
  most_recent_completed_session_id: string | null
}

interface WorkspaceStatusResponse {
  knowledge_graph_id: string
  workspace_mode: 'schema_bootstrap' | 'extraction_operations'
  readiness: WorkspaceReadinessStatus
  transition_eligible: boolean
  session_pointers: WorkspaceSessionPointers
}

const route = useRoute()
const { hasTenant, tenantVersion } = useTenant()
const { extractErrorMessage } = useErrorHandler()
const { apiFetch } = useApiClient()
const kgId = computed(() => String(route.params.kgId ?? ''))
const loading = ref(false)
const validating = ref(false)
const transitioning = ref(false)
const statusProjection = ref<WorkspaceStatusResponse | null>(null)

const modeLabel = computed(() =>
  statusProjection.value?.workspace_mode === 'extraction_operations'
    ? 'Extraction Operations'
    : 'Schema Bootstrap',
)

const canTransition = computed(() =>
  statusProjection.value?.workspace_mode === 'schema_bootstrap'
  && statusProjection.value?.transition_eligible === true,
)

async function loadWorkspaceStatus() {
  if (!hasTenant.value || !kgId.value) return
  loading.value = true
  try {
    statusProjection.value = await apiFetch<WorkspaceStatusResponse>(
      `/management/knowledge-graphs/${kgId.value}/workspace-status`,
    )
  } catch (err) {
    statusProjection.value = null
    toast.error('Failed to load knowledge graph workspace', {
      description: extractErrorMessage(err),
    })
  } finally {
    loading.value = false
  }
}

async function validateWorkspace() {
  if (!kgId.value) return
  validating.value = true
  try {
    statusProjection.value = await apiFetch<WorkspaceStatusResponse>(
      `/management/knowledge-graphs/${kgId.value}/workspace/validate`,
      { method: 'POST' },
    )
    toast.success('Workspace validation complete')
  } catch (err) {
    toast.error('Validation failed', {
      description: extractErrorMessage(err),
    })
  } finally {
    validating.value = false
  }
}

async function transitionToExtraction() {
  if (!kgId.value || !canTransition.value) return
  transitioning.value = true
  try {
    statusProjection.value = await apiFetch<WorkspaceStatusResponse>(
      `/management/knowledge-graphs/${kgId.value}/workspace/transition-to-extraction`,
      { method: 'POST' },
    )
    toast.success('Workspace transitioned to extraction operations')
    navigateTo(`/graph/mutations?kg_id=${kgId.value}&view=editor`)
  } catch (err) {
    toast.error('Transition failed', {
      description: extractErrorMessage(err),
    })
  } finally {
    transitioning.value = false
  }
}

onMounted(() => {
  loadWorkspaceStatus()
})

watch(tenantVersion, () => {
  statusProjection.value = null
  loadWorkspaceStatus()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div class="space-y-1">
        <div class="flex items-center gap-2">
          <h1 class="text-2xl font-semibold tracking-tight">Knowledge Graph Manage Workspace</h1>
          <Badge variant="secondary">{{ modeLabel }}</Badge>
        </div>
        <p class="text-sm text-muted-foreground">
          Validate readiness and move from schema bootstrap to extraction operations.
        </p>
      </div>
      <Button variant="outline" size="sm" @click="navigateTo('/knowledge-graphs')">
        <ArrowLeft class="mr-1.5 size-3.5" />
        Back to Knowledge Graphs
      </Button>
    </div>

    <Separator />

    <div v-if="!hasTenant" class="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
      Select a tenant to manage this workspace.
    </div>

    <div v-else-if="loading" class="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 class="size-4 animate-spin" />
      Loading workspace status...
    </div>

    <template v-else-if="statusProjection">
      <Card>
        <CardHeader>
          <CardTitle class="text-base">Mode & Transition Controls</CardTitle>
          <CardDescription>
            Validate current readiness and transition when eligible.
          </CardDescription>
        </CardHeader>
        <CardContent class="flex flex-wrap gap-2">
          <Button variant="outline" :disabled="validating || transitioning" @click="validateWorkspace">
            <Loader2 v-if="validating" class="mr-1.5 size-3.5 animate-spin" />
            <CheckCircle2 v-else class="mr-1.5 size-3.5" />
            Validate
          </Button>
          <Button
            :disabled="!canTransition || transitioning || validating"
            @click="transitionToExtraction"
          >
            <Loader2 v-if="transitioning" class="mr-1.5 size-3.5 animate-spin" />
            <PlayCircle v-else class="mr-1.5 size-3.5" />
            Go to Extraction/Mutations
          </Button>
          <Badge :variant="canTransition ? 'default' : 'secondary'">
            {{ canTransition ? 'Transition eligible' : 'Transition blocked' }}
          </Badge>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle class="text-base">Readiness Results</CardTitle>
          <CardDescription>
            Bootstrap readiness requirements from workspace validation.
          </CardDescription>
        </CardHeader>
        <CardContent class="space-y-2 text-sm">
          <div class="flex items-center justify-between rounded border px-3 py-2">
            <span>Has minimum entity types</span>
            <Badge :variant="statusProjection.readiness.has_minimum_entity_types ? 'default' : 'destructive'">
              {{ statusProjection.readiness.has_minimum_entity_types ? 'Yes' : 'No' }}
            </Badge>
          </div>
          <div class="flex items-center justify-between rounded border px-3 py-2">
            <span>Has minimum relationship types</span>
            <Badge :variant="statusProjection.readiness.has_minimum_relationship_types ? 'default' : 'destructive'">
              {{ statusProjection.readiness.has_minimum_relationship_types ? 'Yes' : 'No' }}
            </Badge>
          </div>
          <div class="flex items-center justify-between rounded border px-3 py-2">
            <span>Prepopulated types ready</span>
            <Badge :variant="statusProjection.readiness.prepopulated_types_ready ? 'default' : 'destructive'">
              {{ statusProjection.readiness.prepopulated_types_ready ? 'Yes' : 'No' }}
            </Badge>
          </div>
          <div v-if="statusProjection.readiness.blocking_reasons.length > 0" class="rounded border border-destructive/50 p-3">
            <p class="mb-1 text-xs font-medium text-destructive flex items-center gap-1.5">
              <ShieldAlert class="size-3.5" />
              Blocking reasons
            </p>
            <ul class="list-disc pl-4 text-xs text-muted-foreground space-y-1">
              <li v-for="reason in statusProjection.readiness.blocking_reasons" :key="reason">
                {{ reason }}
              </li>
            </ul>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle class="text-base">Session Pointers</CardTitle>
          <CardDescription>
            Active and recent extraction session references for this knowledge graph.
          </CardDescription>
        </CardHeader>
        <CardContent class="grid gap-2 md:grid-cols-3 text-xs">
          <div class="rounded border px-3 py-2">
            <p class="text-muted-foreground">Active schema bootstrap session</p>
            <p class="font-mono break-all mt-1">
              {{ statusProjection.session_pointers.active_schema_bootstrap_session_id ?? 'None' }}
            </p>
          </div>
          <div class="rounded border px-3 py-2">
            <p class="text-muted-foreground">Active extraction operations session</p>
            <p class="font-mono break-all mt-1">
              {{ statusProjection.session_pointers.active_extraction_operations_session_id ?? 'None' }}
            </p>
          </div>
          <div class="rounded border px-3 py-2">
            <p class="text-muted-foreground">Most recent completed session</p>
            <p class="font-mono break-all mt-1">
              {{ statusProjection.session_pointers.most_recent_completed_session_id ?? 'None' }}
            </p>
          </div>
        </CardContent>
      </Card>
    </template>
  </div>
</template>
