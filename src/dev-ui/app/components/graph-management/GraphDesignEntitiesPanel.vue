<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { ChevronDown, Loader2, RefreshCw } from 'lucide-vue-next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  type DesignArtifactEntityType,
  type DesignArtifactsResponse,
  pageSlice,
  prepopulationBadgeClass,
  prepopulationCardClass,
  prepopulationLabel,
} from '@/utils/kgDesignArtifacts'

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
const instancePage = ref<Record<string, number>>({})

async function fetchEntities(options: { preserveUiState?: boolean } = {}) {
  if (!props.kgId) {
    data.value = null
    loading.value = false
    return
  }
  const preserveUiState = options.preserveUiState === true && data.value !== null
  if (!preserveUiState) {
    loading.value = true
    instancePage.value = {}
  }
  try {
    data.value = await apiFetch<DesignArtifactsResponse>(
      `/management/knowledge-graphs/${props.kgId}/design-artifacts`,
      { query: { limit: 500 } },
    )
  } catch (err: unknown) {
    toast.error('Failed to load entity design artifacts', {
      description: err instanceof Error ? err.message : 'Request failed',
    })
    data.value = null
  } finally {
    loading.value = false
  }
}

const entityRows = computed((): DesignArtifactEntityType[] => {
  if (!data.value?.entities) return []
  return Object.entries(data.value.entities).map(([type, def]) => ({
    type,
    ...def,
  }))
})

function setInstancePage(typeKey: string, page: number) {
  instancePage.value = { ...instancePage.value, [typeKey]: page }
}

watch(
  () => [props.kgId, props.reloadNonce] as const,
  ([, reloadNonce]) => {
    void fetchEntities({ preserveUiState: reloadNonce > 0 })
  },
  { immediate: true },
)

defineExpose({ refresh: fetchEntities })
</script>

<template>
  <div :class="embedded ? 'space-y-2' : 'mx-auto max-w-4xl space-y-4'">
    <div v-if="embedded" class="flex flex-wrap items-center justify-between gap-2 border-b pb-2">
      <div class="min-w-0">
        <h2 class="text-sm font-semibold tracking-tight">Entity ontology</h2>
        <p class="text-[11px] leading-snug text-muted-foreground">
          Schema types and instances for this knowledge graph.
        </p>
      </div>
      <div class="flex items-center gap-2">
        <Badge v-if="data?.counts.entity_types" variant="secondary" class="shrink-0">
          {{ data.counts.entity_types }} type(s)
        </Badge>
        <Button variant="outline" size="sm" :disabled="loading" @click="fetchEntities">
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
      <Card v-if="!data.found || entityRows.length === 0">
        <CardHeader>
          <CardTitle class="text-base">
            <span v-if="!data.found">No ontology saved yet</span>
            <span v-else>No entity types yet</span>
          </CardTitle>
        </CardHeader>
        <CardContent class="space-y-3 text-sm text-muted-foreground">
          <p class="text-foreground">
            Use the Graph Management Assistant above to design entity types and instances. When changes
            are saved to the database, click Refresh to review them here.
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

        <div class="space-y-1.5">
          <Card
            v-for="row in entityRows"
            :key="row.type"
            :class="['overflow-hidden', prepopulationCardClass(row.prepopulated_instances)]"
          >
            <details class="group">
              <summary
                class="flex cursor-pointer list-none items-center gap-2 px-2.5 py-2 [&::-webkit-details-marker]:hidden"
              >
                <ChevronDown
                  class="size-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
                />
                <div class="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
                  <span class="text-sm font-semibold leading-tight">{{ row.type }}</span>
                  <Badge
                    variant="outline"
                    class="h-5 px-1.5 text-[10px]"
                    :class="prepopulationBadgeClass(row.prepopulated_instances)"
                  >
                    {{ prepopulationLabel(row.prepopulated_instances) }}
                  </Badge>
                  <Badge variant="secondary" class="h-5 px-1.5 text-[10px]">
                    {{ row.instance_count }} instance{{ row.instance_count === 1 ? '' : 's' }}
                  </Badge>
                </div>
              </summary>
              <div class="space-y-2 border-t px-2.5 pb-2.5 pt-0">
                <p v-if="row.description" class="pt-2 text-xs leading-snug text-muted-foreground">
                  {{ row.description }}
                </p>
                <div v-else class="pt-1.5 text-xs italic text-muted-foreground">No description</div>

                <div class="space-y-1">
                  <p class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    Properties
                  </p>
                  <div
                    v-if="row.property_definitions && Object.keys(row.property_definitions).length > 0"
                    class="divide-y rounded-md border text-xs"
                  >
                    <div
                      v-for="(label, key) in row.property_definitions"
                      :key="key"
                      class="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 px-2 py-1"
                    >
                      <code class="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">{{ key }}</code>
                      <span class="text-muted-foreground">{{ label }}</span>
                      <Badge
                        v-if="row.required_properties?.includes(String(key))"
                        variant="outline"
                        class="h-4 px-1 text-[9px]"
                      >
                        required
                      </Badge>
                      <Badge
                        v-else-if="row.optional_properties?.includes(String(key))"
                        variant="outline"
                        class="h-4 px-1 text-[9px] opacity-70"
                      >
                        optional
                      </Badge>
                    </div>
                  </div>
                  <p v-else class="text-xs text-muted-foreground">No property definitions</p>
                </div>

                <details v-if="(row.instances?.length ?? 0) > 0" class="group/inst rounded-md border">
                  <summary
                    class="flex cursor-pointer list-none items-center gap-1.5 px-2 py-1.5 text-xs font-medium hover:bg-muted/50 [&::-webkit-details-marker]:hidden"
                  >
                    <ChevronDown
                      class="size-3.5 shrink-0 text-muted-foreground transition-transform group-open/inst:rotate-180"
                    />
                    Instances
                    <span v-if="row.instances_truncated" class="font-normal text-muted-foreground">
                      (showing {{ row.instances_returned ?? row.instances?.length ?? 0 }} of
                      {{ row.instance_count }})
                    </span>
                  </summary>
                  <div class="space-y-2 border-t p-2">
                    <ul class="space-y-1 text-xs">
                      <li
                        v-for="(inst, idx) in pageSlice(instancePage, row.type, row.instances || []).items"
                        :key="inst.slug ?? idx"
                        class="rounded-md bg-muted/40 px-2 py-1"
                      >
                        <div class="mb-0.5 font-mono text-[10px] text-muted-foreground">
                          {{ inst.slug ?? '—' }}
                        </div>
                        <pre class="max-h-24 overflow-y-auto whitespace-pre-wrap break-all text-[10px] leading-snug">{{
                          JSON.stringify(inst.properties ?? {}, null, 2)
                        }}</pre>
                      </li>
                    </ul>
                    <div
                      v-if="pageSlice(instancePage, row.type, row.instances || []).total > 20"
                      class="flex flex-wrap items-center gap-1.5"
                      @click.stop
                    >
                      <Button
                        variant="outline"
                        size="sm"
                        class="h-7 px-2 text-xs"
                        :disabled="pageSlice(instancePage, row.type, row.instances || []).page <= 0"
                        @click.stop.prevent="setInstancePage(row.type, pageSlice(instancePage, row.type, row.instances || []).page - 1)"
                      >
                        Previous
                      </Button>
                      <span class="text-xs text-muted-foreground">
                        Page {{ pageSlice(instancePage, row.type, row.instances || []).page + 1 }} /
                        {{ pageSlice(instancePage, row.type, row.instances || []).totalPages }}
                        ({{ row.instances_truncated ? `${row.instances_returned ?? row.instances?.length ?? 0} loaded of ${row.instance_count}` : pageSlice(instancePage, row.type, row.instances || []).total }} total)
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        class="h-7 px-2 text-xs"
                        :disabled="
                          pageSlice(instancePage, row.type, row.instances || []).page
                            >= pageSlice(instancePage, row.type, row.instances || []).totalPages - 1
                        "
                        @click.stop.prevent="setInstancePage(row.type, pageSlice(instancePage, row.type, row.instances || []).page + 1)"
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                </details>
              </div>
            </details>
          </Card>
        </div>

        <p
          v-if="data.limits.entity_instances_truncated"
          class="text-xs text-muted-foreground"
        >
          Instance counts reflect the full graph. The browsable instance list is capped at
          {{ data.limits.entity_instances_returned }} of {{ data.counts.entity_instances }}
          total instances across all types (API limit {{ data.limits.requested }}). Per-type badges
          still show true totals.
        </p>
      </template>
    </template>
  </div>
</template>
