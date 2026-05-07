<script setup lang="ts">

import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick, markRaw } from 'vue'
import { toast } from 'vue-sonner'
import { Orbit, Building2, Loader2, Search, Pause, Play, Maximize, X } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { VisualizerNode, VisualizerEdge } from '~/types'
import { useApiClient } from '~/composables/useApiClient'

const { getBulkGraphData } = useGraphApi()
const { hasTenant, tenantVersion } = useTenant()
const { extractErrorMessage } = useErrorHandler()

// ── State ──────────────────────────────────────────────────────────────────

const cosmographContainer = ref<HTMLElement | null>(null)
let cosmograph: any = null
let loadAbortController: AbortController | null = null

const isPaused = ref(false)
let rawNodes: VisualizerNode[] = []
let rawEdges: VisualizerEdge[] = []
let linksForTooltip: any[] = []
let preparedLinksRef: any[] = []
const pinnedNodeIndex = ref<number | null>(null)
const mouseX = ref(0)
const mouseY = ref(0)

// Loading
const isLoading = ref(true)
const loadingPhase = ref('Fetching graph data...')
const progressReceived = ref(0)
const progressTotal = ref<number | null>(null)

// Stats
const nodeCount = ref(0)
const edgeCount = ref(0)
const statusText = ref('')

// Metadata panel
const metadataVisible = ref(false)
const metadataTitle = ref('')
const metadataRows = ref<Array<{ key: string; value: string }>>([])

// Edge tooltip
const edgeTooltipVisible = ref(false)
const edgeTooltipType = ref('')
const edgeTooltipNodes = ref('')

// Search
const searchQuery = ref('')

// KG selector
const selectedKgId = ref<string>('')
const knowledgeGraphs = ref<Array<{ id: string; name: string }>>([])
const kgLoading = ref(false)

// Node ID lookup map
let nodeIdToData: Record<string, VisualizerNode> = {}

// ── Mouse tracking ─────────────────────────────────────────────────────────

function onMouseMove(e: MouseEvent) {
  mouseX.value = e.clientX
  mouseY.value = e.clientY
}

// ── Metadata panel ─────────────────────────────────────────────────────────

function showMetadata(node: VisualizerNode, pinned = false) {
  if (!node) {
    if (!pinned && pinnedNodeIndex.value === null) {
      metadataVisible.value = false
    }
    return
  }

  metadataTitle.value = `${node.type}: ${node.label || node.id}`
  metadataRows.value = Object.entries(node)
    .filter(([key]) => key !== 'id')
    .map(([key, value]) => ({
      key,
      value: typeof value === 'object' ? JSON.stringify(value) : String(value),
    }))
  metadataVisible.value = true
}

function hideMetadata() {
  if (pinnedNodeIndex.value === null) {
    metadataVisible.value = false
  }
}

function closeMetadata() {
  pinnedNodeIndex.value = null
  metadataVisible.value = false
}

// ── Edge tooltip ───────────────────────────────────────────────────────────

function showEdgeTooltip(edge: { source: string; target: string; edgeType: string }) {
  const sourceNode = nodeIdToData[edge.source]
  const targetNode = nodeIdToData[edge.target]
  edgeTooltipType.value = edge.edgeType || 'unknown'
  edgeTooltipNodes.value = `${sourceNode?.label || edge.source} → ${targetNode?.label || edge.target}`
  edgeTooltipVisible.value = true
}

function hideEdgeTooltip() {
  edgeTooltipVisible.value = false
}

// ── KG list ────────────────────────────────────────────────────────────────

async function loadKnowledgeGraphs() {
  if (!hasTenant.value) return
  kgLoading.value = true
  try {
    const { apiFetch } = useApiClient()
    const result = await apiFetch<{ knowledge_graphs: Array<{ id: string; name: string }> }>(
      '/management/knowledge-graphs',
    )
    knowledgeGraphs.value = result.knowledge_graphs ?? []
    if (!selectedKgId.value) {
      selectedKgId.value = '__all__'
    }
  } catch (err) {
    toast.error('Failed to load knowledge graphs', { description: extractErrorMessage(err) })
  } finally {
    kgLoading.value = false
  }
}

// ── Graph loading ──────────────────────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const progressText = computed(() => {
  if (progressTotal.value) {
    return `${formatBytes(progressReceived.value)} / ${formatBytes(progressTotal.value)}`
  }
  if (progressReceived.value > 0) {
    return `${formatBytes(progressReceived.value)} received`
  }
  return 'Connecting...'
})

const progressPercent = computed(() => {
  if (progressTotal.value && progressTotal.value > 0) {
    return Math.round((progressReceived.value / progressTotal.value) * 100)
  }
  return progressReceived.value > 0 ? 50 : 0
})

async function loadGraphData() {
  if (loadAbortController) loadAbortController.abort()
  loadAbortController = new AbortController()
  const signal = loadAbortController.signal

  isLoading.value = true
  loadingPhase.value = 'Fetching graph data...'
  progressReceived.value = 0
  progressTotal.value = null

  if (cosmograph) {
    cosmograph.destroy()
    cosmograph = null
  }

  try {
    const data = await getBulkGraphData(
      selectedKgId.value === '__all__' ? undefined : selectedKgId.value || undefined,
      {
        signal,
        onProgress: (received, total) => {
          progressReceived.value = received
          progressTotal.value = total
        },
      },
    )

    loadingPhase.value = 'Preparing visualization...'
    rawNodes = data.nodes || []
    rawEdges = data.edges || []
    nodeCount.value = rawNodes.length
    edgeCount.value = rawEdges.length

    if (nodeCount.value === 0) {
      loadingPhase.value = 'No nodes in graph. Add some data first.'
      statusText.value = 'Empty graph'
      return
    }

    nodeIdToData = {}
    rawNodes.forEach((node) => {
      nodeIdToData[node.id] = node
    })

    await initCosmograph()
  } catch (err) {
    loadingPhase.value = `Error: ${extractErrorMessage(err)}`
    statusText.value = 'Error loading graph'
    toast.error('Failed to load graph data', { description: extractErrorMessage(err) })
  }
}

async function initCosmograph() {
  if (!cosmographContainer.value) return

  // Wait for the container to have dimensions — Cosmograph reads the
  // canvas size at init and won't update the WebGL viewport if it starts at 0x0.
  await nextTick()
  const el = cosmographContainer.value
  if (!el.offsetWidth || !el.offsetHeight) {
    await new Promise<void>((resolve) => {
      const ro = new ResizeObserver(() => {
        if (el.offsetWidth && el.offsetHeight) {
          ro.disconnect()
          resolve()
        }
      })
      ro.observe(el)
    })
  }

  const { Cosmograph, prepareCosmographData } = await import('@cosmograph/cosmograph')

  const points = rawNodes.map((n) => ({
    id: n.id,
    label: n.label || n.id,
    nodeType: n.type || 'unknown',
  }))

  const links = rawEdges.map((e) => ({
    source: e.source,
    target: e.target,
    edgeType: e.type || 'unknown',
  }))

  linksForTooltip = links

  const hasLinks = links.length > 0
  const dataConfig = {
    points: {
      pointIdBy: 'id',
      pointLabelBy: 'label',
      pointColorBy: 'nodeType',
    },
    ...(hasLinks && {
      links: {
        linkSourceBy: 'source',
        linkTargetsBy: ['target'],
      },
    }),
    pointSizeBy: 'degree',
    pointSizeRange: [1, 100],
  }

  statusText.value = 'Preparing graph data...'

  const result = await prepareCosmographData(dataConfig, points, hasLinks ? links : undefined)
  if (!result) throw new Error('Failed to prepare data')

  const { points: preparedPoints, links: preparedLinks, cosmographConfig } = result
  preparedLinksRef = preparedLinks ? Array.from(preparedLinks) : []

  isLoading.value = false
  statusText.value = 'Running simulation...'
  isPaused.value = false

  // Pass the raw DOM element to Cosmograph — cosmographContainer is a Vue
  // ref, and passing .value directly can leak Vue's Proxy into Cosmograph
  // internals, causing "proxy must report same extensibility as target".
  const rawEl = cosmographContainer.value!
  cosmograph = markRaw(new Cosmograph(rawEl, {
    ...cosmographConfig,
    points: preparedPoints,
    ...(preparedLinks && { links: preparedLinks }),
    backgroundColor: '#0a0a0a',
    linkWidth: 0.5,
    linkArrows: false,
    linkColor: '#555555',
    hoveredLinkColor: '#4fc3f7',
    hoveredLinkWidthIncrease: 3,
    hoveredLinkCursor: 'pointer',
    hoveredPointRingColor: '#ffffff',
    focusedPointRingColor: '#4fc3f7',
    simulationGravity: 0.1,
    simulationRepulsion: 1.0,
    simulationLinkSpring: 0.5,
    simulationFriction: 0.9,
    onSimulationEnd: () => {
      statusText.value = 'Layout complete'
    },
    onPointMouseOver: (index: number) => {
      if (index !== undefined && index !== null && rawNodes[index]) {
        showMetadata(rawNodes[index], false)
      }
    },
    onPointMouseOut: () => {
      hideMetadata()
    },
    onPointClick: (index: number) => {
      if (index !== undefined && index !== null && rawNodes[index]) {
        pinnedNodeIndex.value = index
        showMetadata(rawNodes[index], true)
      }
    },
    onLinkMouseOver: (linkIndex: number) => {
      const link = preparedLinksRef?.[linkIndex]
      if (link) {
        const sourceNode = rawNodes[link.sourceidx]
        const targetNode = rawNodes[link.targetidx]
        if (sourceNode && targetNode) {
          const matchingLink = linksForTooltip.find(
            (l: any) => l.source === sourceNode.id && l.target === targetNode.id,
          )
          showEdgeTooltip({
            source: sourceNode.id,
            target: targetNode.id,
            edgeType: matchingLink?.edgeType || 'unknown',
          })
        }
      }
    },
    onLinkMouseOut: () => {
      hideEdgeTooltip()
    },
  }))
}

// ── Controls ───────────────────────────────────────────────────────────────

function togglePause() {
  if (!cosmograph) return
  isPaused.value = !isPaused.value
  if (isPaused.value) {
    cosmograph.pause()
    statusText.value = 'Paused'
  } else {
    cosmograph.unpause()
    statusText.value = 'Running simulation...'
  }
}

function fitView() {
  if (!cosmograph) return
  cosmograph.pause()
  isPaused.value = true
  statusText.value = 'Paused'
  setTimeout(() => cosmograph?.fitView(500), 50)
}

// ── Search ─────────────────────────────────────────────────────────────────

watch(searchQuery, (query) => {
  if (!cosmograph) return

  const q = query.toLowerCase().trim()
  if (!q) {
    cosmograph.unselectAllPoints()
    statusText.value = isPaused.value ? 'Paused' : 'Layout complete'
    return
  }

  const matchingIndices: number[] = []
  rawNodes.forEach((node, index) => {
    const fields = [node.label, node.type, node.domainId, (node as any).name, (node as any).slug]
      .filter(Boolean)
      .map((s) => String(s).toLowerCase())
    if (fields.some((field) => field.includes(q))) {
      matchingIndices.push(index)
    }
  })

  if (matchingIndices.length > 0) {
    cosmograph.selectPoints(matchingIndices)
    statusText.value = `${matchingIndices.length} matches`
    if (matchingIndices.length === 1) {
      cosmograph.zoomToPoint(matchingIndices[0], 1000)
    }
  } else {
    cosmograph.unselectAllPoints()
    statusText.value = 'No matches'
  }
})

// ── KG switch ──────────────────────────────────────────────────────────────

watch(selectedKgId, (newId, oldId) => {
  if (newId && newId !== oldId && oldId !== '') {
    loadGraphData()
  }
})

// ── Tenant switch ──────────────────────────────────────────────────────────

watch(tenantVersion, () => {
  selectedKgId.value = '__all__'
  knowledgeGraphs.value = []
  if (!hasTenant.value) return
  loadKnowledgeGraphs().then(() => {
    if (selectedKgId.value && hasTenant.value) loadGraphData()
  })
})

// ── Lifecycle ──────────────────────────────────────────────────────────────

onMounted(() => {
  document.addEventListener('mousemove', onMouseMove)
  if (hasTenant.value) {
    loadKnowledgeGraphs().then(() => {
      if (selectedKgId.value) loadGraphData()
    })
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onMouseMove)
  if (cosmograph) {
    cosmograph.destroy()
    cosmograph = null
  }
})
</script>

<template>
  <div class="fixed inset-0 bg-[#0a0a0a]" style="z-index: 35;">
    <!-- Cosmograph container -->
    <div ref="cosmographContainer" style="width: 100vw; height: 100vh;" />

    <!-- No tenant -->
    <div
      v-if="!hasTenant"
      class="absolute inset-0 flex flex-col items-center justify-center gap-3 text-center text-muted-foreground"
    >
      <Building2 class="size-10 text-gray-500" />
      <p class="font-medium text-white">No tenant selected</p>
      <p class="text-sm text-gray-400">Select a tenant from the sidebar to visualize a graph.</p>
    </div>

    <!-- Loading overlay -->
    <div
      v-if="isLoading && hasTenant"
      class="absolute inset-0 flex flex-col items-center justify-center gap-4 text-center"
    >
      <div class="text-lg text-gray-400">{{ loadingPhase }}</div>
      <div class="space-y-2">
        <span class="text-sm text-[#4fc3f7]">{{ progressText }}</span>
        <div class="w-[300px] h-1 bg-gray-700 rounded-full overflow-hidden">
          <div
            class="h-full bg-[#4fc3f7] rounded-full transition-all duration-300"
            :style="{ width: `${progressPercent}%` }"
          />
        </div>
      </div>
    </div>

    <!-- Control panel (top-left) -->
    <div
      v-if="hasTenant"
      class="absolute top-4 left-4 z-40 min-w-[280px] rounded-lg p-4 shadow-lg"
      style="background: rgba(20, 20, 20, 0.95)"
    >
      <div class="flex items-center gap-2 mb-3">
        <button
          class="text-gray-400 hover:text-white text-sm"
          @click="navigateTo('/')"
        >
          ← Back
        </button>
        <Orbit class="size-4 text-[#4fc3f7]" />
        <h1 class="text-base font-semibold text-white">Graph Visualizer</h1>
      </div>

      <!-- KG selector -->
      <div class="mb-3">
        <Select v-model="selectedKgId">
          <SelectTrigger class="w-full bg-[#1a1a1a] border-gray-600 text-white text-sm">
            <SelectValue placeholder="Select knowledge graph..." />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">
              All Knowledge Graphs
            </SelectItem>
            <SelectItem
              v-for="kg in knowledgeGraphs"
              :key="kg.id"
              :value="kg.id"
            >
              {{ kg.name }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      <!-- Search -->
      <div class="relative mb-3">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-gray-500" />
        <Input
          v-model="searchQuery"
          placeholder="Search nodes..."
          class="pl-9 bg-[#1a1a1a] border-gray-600 text-white text-sm placeholder:text-gray-500"
        />
      </div>

      <!-- Controls -->
      <div class="flex gap-2 mb-3">
        <Button
          variant="secondary"
          size="sm"
          class="bg-gray-700 hover:bg-gray-600 text-white text-xs"
          @click="fitView"
        >
          <Maximize class="mr-1 size-3" />
          Fit to Screen
        </Button>
        <Button
          variant="secondary"
          size="sm"
          class="bg-gray-700 hover:bg-gray-600 text-white text-xs"
          @click="togglePause"
        >
          <component :is="isPaused ? Play : Pause" class="mr-1 size-3" />
          {{ isPaused ? 'Play' : 'Pause' }}
        </Button>
      </div>

      <!-- Stats -->
      <div class="text-xs text-gray-500">
        Nodes: <span class="text-[#4fc3f7] font-semibold">{{ nodeCount.toLocaleString() }}</span> |
        Edges: <span class="text-[#4fc3f7] font-semibold">{{ edgeCount.toLocaleString() }}</span>
      </div>
      <div v-if="statusText" class="text-[11px] text-gray-500 mt-1">{{ statusText }}</div>
    </div>

    <!-- Metadata panel (top-right) -->
    <div
      v-if="metadataVisible"
      class="absolute top-4 right-4 z-40 min-w-[320px] max-w-[400px] max-h-[80vh] overflow-y-auto rounded-lg p-4 shadow-lg"
      style="background: rgba(20, 20, 20, 0.95)"
    >
      <button
        class="absolute top-2 right-2 text-gray-500 hover:text-white text-lg leading-none"
        @click="closeMetadata"
      >
        <X class="size-4" />
      </button>
      <h2 class="text-sm font-semibold text-[#4fc3f7] mb-3">{{ metadataTitle }}</h2>
      <table class="w-full border-collapse">
        <tr v-for="row in metadataRows" :key="row.key" class="border-b border-gray-700">
          <td class="px-2 py-1 text-xs text-gray-500 font-medium whitespace-nowrap align-top w-[100px]">
            {{ row.key }}
          </td>
          <td class="px-2 py-1 text-xs text-white break-words">{{ row.value }}</td>
        </tr>
      </table>
      <div class="text-[11px] text-gray-600 mt-2 italic">Click a node to pin details</div>
    </div>

    <!-- Edge tooltip (follows cursor) -->
    <div
      v-if="edgeTooltipVisible"
      class="fixed z-40 rounded-md px-3 py-2 text-xs pointer-events-none shadow-lg border border-gray-700 max-w-[300px]"
      style="background: rgba(20, 20, 20, 0.95)"
      :style="{ left: `${mouseX + 12}px`, top: `${mouseY + 12}px` }"
    >
      <div class="text-[#4fc3f7] font-semibold text-[13px]">{{ edgeTooltipType }}</div>
      <div class="text-gray-500 text-[11px] mt-1">{{ edgeTooltipNodes }}</div>
    </div>
  </div>
</template>
