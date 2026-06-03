<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { ChevronDown, Loader2, RefreshCw, Search } from 'lucide-vue-next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  type DesignArtifactRelationshipType,
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

async function fetchRelationships() {
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
    toast.error('Failed to load relationship design artifacts', {
      description: err instanceof Error ? err.message : 'Request failed',
    })
    data.value = null
  } finally {
    loading.value = false
  }
}

const relationshipRows = computed(() => data.value?.relationships ?? [])

const filteredRows = computed(() => {
  const query = filterText.value.trim().toLowerCase()
  if (!query) return relationshipRows.value
  return relationshipRows.value.filter((rel) => {
    return (
      rel.relationship_type.toLowerCase().includes(query)
      || (rel.reverse_relationship_type ?? '').toLowerCase().includes(query)
      || rel.source_entity_type.toLowerCase().includes(query)
      || rel.target_entity_type.toLowerCase().includes(query)
      || rel.key.toLowerCase().includes(query)
    )
  })
})

function setInstancePage(key: string, page: number) {
  instancePage.value = { ...instancePage.value, [key]: page }
}

watch(filterText, () => {
  instancePage.value = {}
})

watch(
  () => [props.kgId, props.reloadNonce] as const,
  () => {
    void fetchRelationships()
  },
  { immediate: true },
)

defineExpose({ refresh: fetchRelationships })
</script>

<template>
  <div :class="embedded ? 'space-y-4' : 'mx-auto max-w-4xl space-y-6'">
    <div v-if="embedded" class="flex flex-wrap items-start justify-between gap-2 border-b pb-3">
      <div>
        <h2 class="text-lg font-semibold tracking-tight">Relationship ontology</h2>
        <p class="text-xs text-muted-foreground">
          Canonical relationship types and live edge instances from the platform database.
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

    <div v-if="loading" class="flex items-center justify-center py-16">
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
                placeholder="Search by relationship, source, or target type…"
                class="flex h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
          </CardContent>
        </Card>

        <div class="space-y-3">
          <p v-if="filteredRows.length === 0" class="py-4 text-center text-sm text-muted-foreground">
            No relationship types match your search.
          </p>

          <Card
            v-for="rel in filteredRows"
            :key="rel.key"
            :class="['overflow-hidden', prepopulationCardClass(rel.prepopulated_instances)]"
          >
            <details class="group">
              <summary class="flex cursor-pointer list-none items-start gap-3 p-4 [&::-webkit-details-marker]:hidden">
                <ChevronDown
                  class="mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
                />
                <div class="min-w-0 flex-1 space-y-1">
                  <div class="flex min-w-0 flex-wrap items-center gap-2">
                    <span class="text-sm font-semibold text-foreground">{{ rel.source_entity_type }}</span>
                    <Badge variant="secondary" class="font-mono text-xs">{{ rel.relationship_type }}</Badge>
                    <template v-if="rel.reverse_relationship_type">
                      <span class="text-xs text-muted-foreground">/</span>
                      <Badge variant="outline" class="font-mono text-xs">{{ rel.reverse_relationship_type }}</Badge>
                    </template>
                    <Badge variant="outline" :class="prepopulationBadgeClass(rel.prepopulated_instances)">
                      {{ prepopulationLabel(rel.prepopulated_instances) }}
                    </Badge>
                    <span class="text-sm text-muted-foreground">→</span>
                    <span class="text-sm font-semibold text-foreground">{{ rel.target_entity_type }}</span>
                    <Badge variant="outline" class="ml-auto">
                      {{ rel.instance_count }} instance{{ rel.instance_count === 1 ? '' : 's' }}
                    </Badge>
                  </div>
                  <p class="truncate text-xs text-muted-foreground">{{ rel.key }}</p>
                </div>
              </summary>
              <div class="space-y-4 border-t px-4 pb-4 pt-3">
                <p v-if="rel.description" class="text-sm text-muted-foreground">{{ rel.description }}</p>

                <div class="space-y-2">
                  <p class="text-xs font-medium uppercase tracking-wide text-muted-foreground">Parameters</p>
                  <div
                    v-if="rel.parameter_definitions && Object.keys(rel.parameter_definitions).length > 0"
                    class="divide-y rounded-md border"
                  >
                    <div
                      v-for="(label, key) in rel.parameter_definitions"
                      :key="key"
                      class="flex flex-wrap gap-x-2 gap-y-1 px-3 py-2 text-sm"
                    >
                      <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{{ key }}</code>
                      <span class="text-muted-foreground">{{ label }}</span>
                    </div>
                  </div>
                  <p v-else class="text-sm text-muted-foreground">No parameter definitions</p>
                </div>

                <details v-if="rel.instances.length > 0" class="group/inst rounded-lg border">
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
                        v-for="(inst, idx) in pageSlice(instancePage, rel.key, rel.instances).items"
                        :key="`${rel.key}-${idx}`"
                        class="rounded-md bg-muted/40 px-3 py-2"
                      >
                        <div class="mb-1 font-mono text-xs text-muted-foreground">
                          {{ inst.source_slug }} --{{ rel.relationship_type }}--> {{ inst.target_slug }}
                        </div>
                        <pre class="whitespace-pre-wrap break-all text-xs">{{
                          JSON.stringify(inst.properties ?? {}, null, 2)
                        }}</pre>
                      </li>
                    </ul>
                  </div>
                </details>
              </div>
            </details>
          </Card>
        </div>

        <p
          v-if="data.limits.relationship_instances_truncated"
          class="text-xs text-muted-foreground"
        >
          Showing the first {{ data.limits.relationship_instances_returned }} of
          {{ data.counts.relationship_instances }} relationship instances.
        </p>
      </template>
    </template>
  </div>
</template>
