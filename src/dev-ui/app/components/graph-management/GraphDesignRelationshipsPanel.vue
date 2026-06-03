<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { ChevronDown, Loader2, RefreshCw } from 'lucide-vue-next'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
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

function setInstancePage(key: string, page: number) {
  instancePage.value = { ...instancePage.value, [key]: page }
}

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
  <div :class="embedded ? 'space-y-2' : 'mx-auto max-w-4xl space-y-4'">
    <div v-if="embedded" class="flex flex-wrap items-center justify-between gap-2 border-b pb-2">
      <div class="min-w-0">
        <h2 class="text-sm font-semibold tracking-tight">Relationship ontology</h2>
        <p class="text-[11px] leading-snug text-muted-foreground">
          Relationship types and instances for this knowledge graph.
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
            v-for="rel in relationshipRows"
            :key="rel.key"
            :class="['overflow-hidden', prepopulationCardClass(rel.prepopulated_instances)]"
          >
            <details class="group">
              <summary
                class="flex cursor-pointer list-none items-start gap-2 px-2.5 py-2 [&::-webkit-details-marker]:hidden"
              >
                <ChevronDown
                  class="mt-0.5 size-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
                />
                <div class="min-w-0 flex-1 space-y-0.5">
                  <div class="flex min-w-0 flex-wrap items-center gap-1.5">
                    <span class="text-sm font-semibold leading-tight text-foreground">{{
                      rel.source_entity_type
                    }}</span>
                    <Badge variant="secondary" class="h-5 px-1.5 font-mono text-[10px]">{{
                      rel.relationship_type
                    }}</Badge>
                    <template v-if="rel.reverse_relationship_type">
                      <span class="text-[10px] text-muted-foreground">/</span>
                      <Badge variant="outline" class="h-5 px-1.5 font-mono text-[10px]">{{
                        rel.reverse_relationship_type
                      }}</Badge>
                    </template>
                    <Badge
                      variant="outline"
                      class="h-5 px-1.5 text-[10px]"
                      :class="prepopulationBadgeClass(rel.prepopulated_instances)"
                    >
                      {{ prepopulationLabel(rel.prepopulated_instances) }}
                    </Badge>
                    <span class="text-xs text-muted-foreground">→</span>
                    <span class="text-sm font-semibold leading-tight text-foreground">{{
                      rel.target_entity_type
                    }}</span>
                    <Badge variant="outline" class="h-5 px-1.5 text-[10px]">
                      {{ rel.instance_count }} instance{{ rel.instance_count === 1 ? '' : 's' }}
                    </Badge>
                  </div>
                  <p class="truncate font-mono text-[10px] text-muted-foreground">{{ rel.key }}</p>
                </div>
              </summary>
              <div class="space-y-2 border-t px-2.5 pb-2.5 pt-0">
                <p v-if="rel.description" class="pt-2 text-xs leading-snug text-muted-foreground">
                  {{ rel.description }}
                </p>
                <div v-else class="pt-1.5 text-xs italic text-muted-foreground">No description</div>

                <div class="space-y-1">
                  <p class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    Parameters
                  </p>
                  <div
                    v-if="rel.parameter_definitions && Object.keys(rel.parameter_definitions).length > 0"
                    class="divide-y rounded-md border text-xs"
                  >
                    <div
                      v-for="(label, key) in rel.parameter_definitions"
                      :key="key"
                      class="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 px-2 py-1"
                    >
                      <code class="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">{{ key }}</code>
                      <span class="text-muted-foreground">{{ label }}</span>
                    </div>
                  </div>
                  <p v-else class="text-xs text-muted-foreground">No parameter definitions</p>
                </div>

                <details v-if="rel.instances.length > 0" class="group/inst rounded-md border">
                  <summary
                    class="flex cursor-pointer list-none items-center gap-1.5 px-2 py-1.5 text-xs font-medium hover:bg-muted/50 [&::-webkit-details-marker]:hidden"
                  >
                    <ChevronDown
                      class="size-3.5 shrink-0 text-muted-foreground transition-transform group-open/inst:rotate-180"
                    />
                    Instances
                  </summary>
                  <div class="space-y-2 border-t p-2">
                    <ul class="space-y-1 text-xs">
                      <li
                        v-for="(inst, idx) in pageSlice(instancePage, rel.key, rel.instances).items"
                        :key="`${rel.key}-${idx}`"
                        class="rounded-md bg-muted/40 px-2 py-1"
                      >
                        <div class="mb-0.5 font-mono text-[10px] text-muted-foreground">
                          {{ inst.source_slug }} --{{ rel.relationship_type }}--> {{ inst.target_slug }}
                        </div>
                        <pre class="max-h-24 overflow-y-auto whitespace-pre-wrap break-all text-[10px] leading-snug">{{
                          JSON.stringify(inst.properties ?? {}, null, 2)
                        }}</pre>
                      </li>
                    </ul>
                    <div
                      v-if="pageSlice(instancePage, rel.key, rel.instances).total > 20"
                      class="flex flex-wrap items-center gap-1.5"
                      @click.stop
                    >
                      <Button
                        variant="outline"
                        size="sm"
                        class="h-7 px-2 text-xs"
                        :disabled="pageSlice(instancePage, rel.key, rel.instances).page <= 0"
                        @click.stop.prevent="
                          setInstancePage(rel.key, pageSlice(instancePage, rel.key, rel.instances).page - 1)
                        "
                      >
                        Previous
                      </Button>
                      <span class="text-xs text-muted-foreground">
                        Page {{ pageSlice(instancePage, rel.key, rel.instances).page + 1 }} /
                        {{ pageSlice(instancePage, rel.key, rel.instances).totalPages }}
                        ({{ pageSlice(instancePage, rel.key, rel.instances).total }} total)
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        class="h-7 px-2 text-xs"
                        :disabled="
                          pageSlice(instancePage, rel.key, rel.instances).page
                            >= pageSlice(instancePage, rel.key, rel.instances).totalPages - 1
                        "
                        @click.stop.prevent="
                          setInstancePage(rel.key, pageSlice(instancePage, rel.key, rel.instances).page + 1)
                        "
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
