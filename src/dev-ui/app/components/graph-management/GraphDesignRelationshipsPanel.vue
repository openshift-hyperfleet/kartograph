<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { Loader2, RefreshCw } from 'lucide-vue-next'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import GraphDesignRelationshipTypeList from '@/components/graph-management/GraphDesignRelationshipTypeList.vue'
import { type DesignArtifactsResponse, DEFAULT_DESIGN_ARTIFACTS_INSTANCES_PER_TYPE } from '@/utils/kgDesignArtifacts'

const props = withDefaults(
  defineProps<{
    kgId: string
    reloadNonce?: number
    embedded?: boolean
  }>(),
  { reloadNonce: 0, embedded: true },
)

const { apiFetch } = useApiClient()

const loading = ref(true)
const data = ref<DesignArtifactsResponse | null>(null)

async function fetchRelationships(options: { preserveUiState?: boolean } = {}) {
  if (!props.kgId) {
    data.value = null
    loading.value = false
    return
  }
  const preserveUiState = options.preserveUiState === true && data.value !== null
  if (!preserveUiState) {
    loading.value = true
  }
  try {
    data.value = await apiFetch<DesignArtifactsResponse>(
      `/management/knowledge-graphs/${props.kgId}/design-artifacts`,
      { query: { limit: DEFAULT_DESIGN_ARTIFACTS_INSTANCES_PER_TYPE } },
    )
  } catch (err: unknown) {
    toast.error('Failed to load relationship design artifacts', {
      description: err instanceof Error ? err.message : 'Request failed',
    })
    data.value = null
  } finally {
    loading.value = false
  }
}

const relationshipRows = computed(() => data.value?.relationships ?? [])

watch(
  () => [props.kgId, props.reloadNonce] as const,
  ([, reloadNonce]) => {
    void fetchRelationships({ preserveUiState: reloadNonce > 0 })
  },
  { immediate: true },
)

defineExpose({ refresh: fetchRelationships })
</script>

<template>
  <div :class="embedded ? 'space-y-2' : 'mx-auto max-w-4xl space-y-4'">
    <div v-if="embedded" class="flex flex-wrap items-center justify-between gap-2 border-b pb-2">
      <div class="min-w-0">
        <h2 class="text-sm font-semibold tracking-tight">Relationship ontology</h2>
        <p class="text-[11px] leading-snug text-muted-foreground">
          Primary relationship types (forward / inverse on one row). Inverse types are stored but not listed separately.
        </p>
      </div>
      <div class="flex items-center gap-2">
        <Badge v-if="data?.counts.relationship_types" variant="secondary" class="shrink-0">
          {{ data.counts.relationship_types }} type(s)
        </Badge>
        <Button variant="outline" size="sm" :disabled="loading" @click="fetchRelationships">
          <Loader2 v-if="loading" class="mr-1.5 size-3.5 animate-spin" />
          <RefreshCw v-else class="mr-1.5 size-3.5" />
          Refresh
        </Button>
      </div>
    </div>

    <div v-if="loading && !data" class="flex items-center justify-center py-16">
      <Loader2 class="size-8 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="data">
      <Card v-if="relationshipRows.length === 0">
        <CardHeader>
          <CardTitle class="text-base">No relationship types yet</CardTitle>
        </CardHeader>
        <CardContent class="space-y-3 text-sm text-muted-foreground">
          <p class="text-foreground">
            Use the Graph Management Assistant to define relationship types and instances, then click Refresh.
          </p>
        </CardContent>
      </Card>

      <template v-else>
        <div
          class="flex flex-wrap items-center gap-2 rounded-md border bg-muted/25 px-2.5 py-1.5 text-xs"
          role="note"
          aria-label="Prepopulation strategy color guide"
        >
          <span class="font-medium text-muted-foreground">Prepopulation colors:</span>
          <Badge
            variant="outline"
            class="h-5 border-cyan-500/40 bg-cyan-500/10 px-1.5 text-[10px] text-cyan-700 dark:text-cyan-300"
          >
            true
          </Badge>
          <Badge
            variant="outline"
            class="h-5 border-emerald-500/40 bg-emerald-500/10 px-1.5 text-[10px] text-emerald-700 dark:text-emerald-300"
          >
            false
          </Badge>
        </div>

        <GraphDesignRelationshipTypeList
          :kg-id="kgId"
          :rows="relationshipRows"
          :reload-nonce="reloadNonce"
        />

        <p
          v-if="data.limits.relationship_instances_truncated"
          class="text-xs text-muted-foreground"
        >
          Each relationship type loads the first
          {{ data.limits.instances_per_type ?? data.limits.requested }} instances by default.
          Expand a type to search or load the next batch.
        </p>
      </template>
    </template>
  </div>
</template>
