<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { ChevronDown, Loader2, RefreshCw, Search } from 'lucide-vue-next'
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
const filterText = ref('')
const instancePage = ref<Record<string, number>>({})

async function fetchEntities() {
  if (!props.kgId) {
    data.value = null
    loading.value = false
    return
  }
  loading.value = true
  try {
    data.value = await apiFetch<DesignArtifactsResponse>(
      `/management/knowledge-graphs/${props.kgId}/design-artifacts`,
      { query: { limit: 500 } },
    )
    instancePage.value = {}
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

const filteredRows = computed(() => {
  const query = filterText.value.trim().toLowerCase()
  if (!query) return entityRows.value
  return entityRows.value.filter((row) => row.type.toLowerCase().includes(query))
})

function setInstancePage(typeKey: string, page: number) {
  instancePage.value = { ...instancePage.value, [typeKey]: page }
}

watch(filterText, () => {
  instancePage.value = {}
})

watch(
  () => [props.kgId, props.reloadNonce] as const,
  () => {
    void fetchEntities()
  },
  { immediate: true },
)

defineExpose({ refresh: fetchEntities })
</script>

<template>
  <div :class="embedded ? 'space-y-4' : 'mx-auto max-w-4xl space-y-6'">
    <div v-if="embedded" class="flex flex-wrap items-start justify-between gap-2 border-b pb-3">
      <div>
        <h2 class="text-lg font-semibold tracking-tight">Entity ontology</h2>
        <p class="text-xs text-muted-foreground">
          Canonical schema and live instances from the platform database for this knowledge graph.
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

    <div v-if="loading" class="flex items-center justify-center py-16">
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
        <Card>
          <CardHeader class="pb-3">
            <CardTitle class="text-base">Prepopulation strategy color guide</CardTitle>
            <CardDescription>
              Each entity type is color-coded by its prepopulation requirement.
            </CardDescription>
          </CardHeader>
          <CardContent class="space-y-3 text-sm">
            <div class="flex flex-wrap gap-2">
              <Badge variant="outline" class="border-cyan-500/40 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300">
                true
              </Badge>
              <Badge variant="outline" class="border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">
                false
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader class="pb-3">
            <CardTitle class="text-base">Filter types</CardTitle>
          </CardHeader>
          <CardContent>
            <div class="relative">
              <Search class="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <input
                v-model="filterText"
                type="search"
                placeholder="Search by entity type name…"
                class="flex h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
          </CardContent>
        </Card>

        <div class="space-y-3">
          <p v-if="filteredRows.length === 0" class="py-4 text-center text-sm text-muted-foreground">
            No entity types match your search.
          </p>

          <Card
            v-for="row in filteredRows"
            :key="row.type"
            :class="['overflow-hidden', prepopulationCardClass(row.prepopulated_instances)]"
          >
            <details class="group">
              <summary class="flex cursor-pointer list-none items-start gap-3 p-4 [&::-webkit-details-marker]:hidden">
                <ChevronDown
                  class="mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
                />
                <div class="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                  <span class="text-base font-semibold">{{ row.type }}</span>
                  <Badge variant="outline" :class="prepopulationBadgeClass(row.prepopulated_instances)">
                    {{ prepopulationLabel(row.prepopulated_instances) }}
                  </Badge>
                  <Badge variant="secondary">
                    {{ row.instance_count }} instance{{ row.instance_count === 1 ? '' : 's' }}
                  </Badge>
                </div>
              </summary>
              <div class="space-y-4 border-t px-4 pb-4 pt-0">
                <p v-if="row.description" class="pt-3 text-sm text-muted-foreground">
                  {{ row.description }}
                </p>
                <div v-else class="pt-2 text-sm italic text-muted-foreground">No description</div>

                <div class="space-y-2">
                  <p class="text-xs font-medium uppercase tracking-wide text-muted-foreground">Properties</p>
                  <div
                    v-if="row.property_definitions && Object.keys(row.property_definitions).length > 0"
                    class="divide-y rounded-md border"
                  >
                    <div
                      v-for="(label, key) in row.property_definitions"
                      :key="key"
                      class="flex flex-wrap gap-x-2 gap-y-1 px-3 py-2 text-sm"
                    >
                      <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{{ key }}</code>
                      <span class="text-muted-foreground">{{ label }}</span>
                      <Badge
                        v-if="row.required_properties?.includes(String(key))"
                        variant="outline"
                        class="h-5 text-[10px]"
                      >
                        required
                      </Badge>
                      <Badge
                        v-else-if="row.optional_properties?.includes(String(key))"
                        variant="outline"
                        class="h-5 text-[10px] opacity-70"
                      >
                        optional
                      </Badge>
                    </div>
                  </div>
                  <p v-else class="text-sm text-muted-foreground">No property definitions</p>
                </div>

                <details v-if="(row.instances?.length ?? 0) > 0" class="group/inst rounded-lg border">
                  <summary
                    class="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-sm font-medium hover:bg-muted/50 [&::-webkit-details-marker]:hidden"
                  >
                    <ChevronDown
                      class="size-4 shrink-0 text-muted-foreground transition-transform group-open/inst:rotate-180"
                    />
                    Instances
                  </summary>
                  <div class="space-y-3 border-t p-3">
                    <ul class="space-y-2 text-sm">
                      <li
                        v-for="(inst, idx) in pageSlice(instancePage, row.type, row.instances || []).items"
                        :key="inst.slug ?? idx"
                        class="rounded-md bg-muted/40 px-3 py-2"
                      >
                        <div class="mb-1 font-mono text-xs text-muted-foreground">
                          {{ inst.slug ?? '—' }}
                        </div>
                        <pre class="whitespace-pre-wrap break-all text-xs">{{
                          JSON.stringify(inst.properties ?? {}, null, 2)
                        }}</pre>
                      </li>
                    </ul>
                    <div
                      v-if="pageSlice(instancePage, row.type, row.instances || []).total > 20"
                      class="flex flex-wrap items-center gap-2 pt-1"
                      @click.stop
                    >
                      <Button
                        variant="outline"
                        size="sm"
                        :disabled="pageSlice(instancePage, row.type, row.instances || []).page <= 0"
                        @click.stop.prevent="setInstancePage(row.type, pageSlice(instancePage, row.type, row.instances || []).page - 1)"
                      >
                        Previous
                      </Button>
                      <span class="text-xs text-muted-foreground">
                        Page {{ pageSlice(instancePage, row.type, row.instances || []).page + 1 }} /
                        {{ pageSlice(instancePage, row.type, row.instances || []).totalPages }}
                        ({{ pageSlice(instancePage, row.type, row.instances || []).total }} total)
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
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
          Showing the first {{ data.limits.entity_instances_returned }} of
          {{ data.counts.entity_instances }} entity instances. Increase the API limit to inspect more.
        </p>
      </template>
    </template>
  </div>
</template>
