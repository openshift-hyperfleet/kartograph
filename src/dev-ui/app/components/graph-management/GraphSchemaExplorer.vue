<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { Box, Link2, Loader2, Network, RefreshCw } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import GraphDesignEntityTypeList from '@/components/graph-management/GraphDesignEntityTypeList.vue'
import GraphDesignRelationshipTypeList from '@/components/graph-management/GraphDesignRelationshipTypeList.vue'
import {
  type DesignArtifactEntityType,
  type DesignArtifactsResponse,
} from '@/utils/kgDesignArtifacts'

const props = withDefaults(
  defineProps<{
    kgId: string
    reloadNonce?: number
  }>(),
  { reloadNonce: 0 },
)

const { apiFetch } = useApiClient()

const loading = ref(true)
const data = ref<DesignArtifactsResponse | null>(null)
const activeTab = ref<'entities' | 'relationships'>('entities')
const entityInstancePage = ref<Record<string, number>>({})
const relationshipInstancePage = ref<Record<string, number>>({})

async function fetchArtifacts(options: { preserveUiState?: boolean } = {}) {
  if (!props.kgId) {
    data.value = null
    loading.value = false
    return
  }
  const preserveUiState = options.preserveUiState === true && data.value !== null
  if (!preserveUiState) {
    loading.value = true
    entityInstancePage.value = {}
    relationshipInstancePage.value = {}
  }
  try {
    data.value = await apiFetch<DesignArtifactsResponse>(
      `/management/knowledge-graphs/${props.kgId}/design-artifacts`,
      { query: { limit: 500 } },
    )
  } catch (err: unknown) {
    toast.error('Failed to load graph schema', {
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

const relationshipRows = computed(() => data.value?.relationships ?? [])

const hasSchema = computed(
  () => Boolean(data.value?.found && (entityRows.value.length > 0 || relationshipRows.value.length > 0)),
)

watch(
  () => [props.kgId, props.reloadNonce] as const,
  ([, reloadNonce]) => {
    void fetchArtifacts({ preserveUiState: reloadNonce > 0 })
  },
  { immediate: true },
)

defineExpose({ refresh: fetchArtifacts })
</script>

<template>
  <Card class="overflow-hidden">
    <CardHeader class="gap-3 space-y-0 border-b bg-muted/20 pb-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="space-y-1">
          <CardTitle class="flex items-center gap-2 text-base">
            <Network class="size-4 text-primary" />
            Graph schema &amp; instances
          </CardTitle>
          <CardDescription class="max-w-2xl">
            Unified view of entity and relationship types from the ontology, with live instance
            inventory from the graph database. Expand any type to inspect properties and instances.
          </CardDescription>
        </div>
        <Button variant="outline" size="sm" :disabled="loading" @click="fetchArtifacts">
          <Loader2 v-if="loading" class="mr-1.5 size-3.5 animate-spin" />
          <RefreshCw v-else class="mr-1.5 size-3.5" />
          Refresh
        </Button>
      </div>
      <div v-if="data && hasSchema" class="flex flex-wrap gap-2 pt-1">
        <Badge variant="secondary" class="gap-1.5 px-2.5 py-1">
          <Box class="size-3.5" />
          {{ data.counts.entity_types }} entity type{{ data.counts.entity_types === 1 ? '' : 's' }}
          · {{ data.counts.entity_instances }} instance{{ data.counts.entity_instances === 1 ? '' : 's' }}
        </Badge>
        <Badge variant="secondary" class="gap-1.5 px-2.5 py-1">
          <Link2 class="size-3.5" />
          {{ data.counts.relationship_types }} relationship type{{
            data.counts.relationship_types === 1 ? '' : 's'
          }}
          · {{ data.counts.relationship_instances }} edge instance{{
            data.counts.relationship_instances === 1 ? '' : 's'
          }}
        </Badge>
      </div>
    </CardHeader>

    <CardContent class="p-0">
      <div v-if="loading && !data" class="flex items-center justify-center py-20">
        <Loader2 class="size-8 animate-spin text-muted-foreground" />
      </div>

      <div v-else-if="!data || !hasSchema" class="space-y-3 px-6 py-10 text-center">
        <p class="text-sm font-medium">
          {{ !data?.found ? 'No ontology saved yet' : 'No schema types defined yet' }}
        </p>
        <p class="mx-auto max-w-md text-sm text-muted-foreground">
          Use Graph Management to design entity and relationship types. When changes are saved,
          click Refresh to browse types and instances here.
        </p>
      </div>

      <Tabs v-else v-model="activeTab" class="w-full">
        <div class="border-b px-4 pt-3">
          <TabsList class="grid h-9 w-full max-w-md grid-cols-2">
            <TabsTrigger value="entities" class="gap-1.5 text-xs">
              <Box class="size-3.5" />
              Entities
              <Badge variant="outline" class="ml-0.5 h-4 px-1 text-[10px]">
                {{ entityRows.length }}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="relationships" class="gap-1.5 text-xs">
              <Link2 class="size-3.5" />
              Relationships
              <Badge variant="outline" class="ml-0.5 h-4 px-1 text-[10px]">
                {{ relationshipRows.length }}
              </Badge>
            </TabsTrigger>
          </TabsList>
        </div>

        <div
          class="flex flex-wrap items-center gap-2 border-b bg-muted/15 px-4 py-2 text-xs"
          role="note"
          aria-label="Prepopulation strategy color guide"
        >
          <span class="font-medium text-muted-foreground">Prepopulation:</span>
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
          <span class="text-muted-foreground">
            · Bidirectional pairs show forward / inverse labels on one row
          </span>
        </div>

        <TabsContent value="entities" class="mt-0 space-y-3 px-4 py-4">
          <GraphDesignEntityTypeList
            :rows="entityRows"
            :instance-page="entityInstancePage"
            @update:instance-page="(key, page) => { entityInstancePage = { ...entityInstancePage, [key]: page } }"
          />
          <p
            v-if="data.limits.entity_instances_truncated"
            class="text-xs text-muted-foreground"
          >
            Browsable entity instances capped at {{ data.limits.entity_instances_returned }} of
            {{ data.counts.entity_instances }} total (API limit {{ data.limits.requested }}). Type
            badges show full counts.
          </p>
        </TabsContent>

        <TabsContent value="relationships" class="mt-0 space-y-3 px-4 py-4">
          <GraphDesignRelationshipTypeList
            :rows="relationshipRows"
            :instance-page="relationshipInstancePage"
            @update:instance-page="(key, page) => { relationshipInstancePage = { ...relationshipInstancePage, [key]: page } }"
          />
          <p
            v-if="data.limits.relationship_instances_truncated"
            class="text-xs text-muted-foreground"
          >
            Browsable relationship instances capped at
            {{ data.limits.relationship_instances_returned }} of
            {{ data.counts.relationship_instances }} total (API limit {{ data.limits.requested }}).
          </p>
        </TabsContent>
      </Tabs>
    </CardContent>
  </Card>
</template>
