<script setup lang="ts">
import { ref, computed } from 'vue'
import { AlertTriangle, Loader2 } from 'lucide-vue-next'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import type { CypherResult, GraphData, GraphNode } from '~/types'
import { extractGraphData } from '@/composables/query/graph/useGraphExtraction'
import { useCytoscape } from '@/composables/query/graph/useCytoscape'

import GraphNodeDetail from './GraphNodeDetail.vue'
import GraphLegend from './GraphLegend.vue'
import GraphToolbar from './GraphToolbar.vue'

const props = defineProps<{
  result: CypherResult | null
  executing: boolean
}>()

// -- Data extraction ---------------------------------------------------------

const graphData = computed<GraphData | null>(() => {
  if (!props.result) return null
  return extractGraphData(props.result)
})

const nodeCount = computed(() => graphData.value?.nodes.length ?? 0)
const edgeCount = computed(() => graphData.value?.edges.length ?? 0)
const hasData = computed(() => nodeCount.value > 0)
const tooLarge = computed(() => nodeCount.value > 2000)
const showWarning = computed(() => nodeCount.value > 500 && !tooLarge.value)
const disableAnimations = computed(() => nodeCount.value > 200)

// -- Cytoscape ---------------------------------------------------------------

const canvasContainer = ref<HTMLElement | null>(null)
const currentLayout = ref('fcose')

const {
  selectedNode,
  labelColors,
  zoomToFit,
  searchNode,
  clearSearch,
  changeLayout,
  toggleLabel,
} = useCytoscape(canvasContainer, graphData, {
  layout: currentLayout,
  disableAnimations: computed(() => disableAnimations.value),
})

// -- Detail panel ------------------------------------------------------------

const detailOpen = computed({
  get: () => selectedNode.value !== null,
  set: (v: boolean) => {
    if (!v) selectedNode.value = null
  },
})

function handleLayoutChange(layout: string) {
  currentLayout.value = layout
  changeLayout(layout)
}

function handleSearch(query: string) {
  if (query) {
    searchNode(query)
  } else {
    clearSearch()
  }
}
</script>

<template>
  <div class="flex h-full flex-col">
    <!-- Executing state -->
    <div v-if="props.executing" class="flex flex-1 items-center justify-center">
      <div class="flex items-center gap-2 text-muted-foreground">
        <Loader2 class="size-5 animate-spin" />
        Executing query...
      </div>
    </div>

    <!-- No result -->
    <div v-else-if="!props.result" class="flex flex-1 items-center justify-center">
      <p class="text-sm text-muted-foreground">
        Execute a query to see the graph here.
      </p>
    </div>

    <!-- No graph elements in result -->
    <div v-else-if="!hasData" class="flex flex-1 items-center justify-center">
      <div class="text-center">
        <p class="text-sm text-muted-foreground">
          No nodes or edges found in the query result.
        </p>
        <p class="mt-1 text-xs text-muted-foreground">
          Return node/edge variables (e.g.,
          <code class="rounded bg-muted px-1 py-0.5">MATCH (n)-[r]-&gt;(m) RETURN n, r, m</code>)
        </p>
      </div>
    </div>

    <!-- Too large -->
    <div v-else-if="tooLarge" class="flex flex-1 items-center justify-center p-4">
      <Alert variant="warning" class="max-w-md">
        <AlertTriangle class="size-4" />
        <AlertTitle>Graph too large</AlertTitle>
        <AlertDescription>
          {{ nodeCount.toLocaleString() }} nodes is too many to visualize performantly.
          Add a <code class="rounded bg-muted px-1 py-0.5">LIMIT</code> clause to reduce
          the result set below 2,000 nodes.
        </AlertDescription>
      </Alert>
    </div>

    <!-- Graph view -->
    <template v-else>
      <!-- Warning for large graphs -->
      <Alert v-if="showWarning" variant="warning" class="mx-1 mb-2">
        <AlertTriangle class="size-4" />
        <AlertDescription class="text-xs">
          Large graph ({{ nodeCount.toLocaleString() }} nodes). Labels hidden until
          zoomed in. Performance may vary.
        </AlertDescription>
      </Alert>

      <!-- Toolbar -->
      <GraphToolbar
        :layout="currentLayout"
        :node-count="nodeCount"
        :edge-count="edgeCount"
        @layout-change="handleLayoutChange"
        @zoom-fit="zoomToFit"
        @search="handleSearch"
      />

      <!-- Canvas + Legend + Detail -->
      <div class="relative flex min-h-0 flex-1">
        <!-- Canvas (inline for direct ref access by useCytoscape) -->
        <div
          ref="canvasContainer"
          class="flex-1 rounded-md border bg-slate-950"
          style="min-height: 300px"
        />

        <!-- Legend overlay -->
        <GraphLegend
          :label-colors="labelColors"
          class="absolute bottom-3 left-3"
          @toggle-label="toggleLabel"
        />

        <!-- Node detail panel -->
        <GraphNodeDetail
          :node="selectedNode"
          :open="detailOpen"
          @close="detailOpen = false"
        />
      </div>
    </template>
  </div>
</template>
