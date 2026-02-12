import { shallowRef, ref, watch, onBeforeUnmount, nextTick, type Ref } from 'vue'
import cytoscape from 'cytoscape'
import fcose from 'cytoscape-fcose'
import type { GraphData, GraphNode } from '~/types'
import { createGraphStylesheet, resetLabelColors, getLabelColors } from './graphStyles'
import { layoutPresets, tuneLayout } from './graphLayouts'

// Register the fcose layout extension once at module level
let fcoseRegistered = false
if (!fcoseRegistered) {
  cytoscape.use(fcose)
  fcoseRegistered = true
}

/** Scale wheel sensitivity based on graph size to balance responsiveness and control. */
function getWheelSensitivity(nodeCount: number): number {
  if (nodeCount < 50) return 1.0
  if (nodeCount <= 200) return 0.8
  if (nodeCount <= 500) return 0.6
  return 0.4
}

export function useCytoscape(
  container: Ref<HTMLElement | null>,
  graphData: Ref<GraphData | null>,
  options: {
    layout?: Ref<string>
    disableAnimations?: Ref<boolean>
  } = {},
) {
  const cy = shallowRef<cytoscape.Core | null>(null)
  const selectedNode = ref<GraphNode | null>(null)
  const hoveredNodeId = ref<string | null>(null)
  const labelColors = ref<Map<string, string>>(new Map())
  let resizeObserver: ResizeObserver | null = null

  function initialize() {
    if (!container.value || !graphData.value || graphData.value.nodes.length === 0) {
      return
    }

    // Clean up previous instance
    cy.value?.destroy()
    cy.value = null
    resetLabelColors()

    const data = graphData.value
    const nodeCount = data.nodes.length

    const elements: cytoscape.ElementDefinition[] = [
      ...data.nodes.map(n => ({
        group: 'nodes' as const,
        data: {
          id: n.id,
          label: n.label,
          displayName: n.displayName,
          _properties: n.properties,
        },
      })),
      ...data.edges.map(e => ({
        group: 'edges' as const,
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.label,
          _properties: e.properties,
        },
      })),
    ]

    const layoutName = options.layout?.value ?? 'fcose'
    const baseLayout = layoutPresets[layoutName] ?? layoutPresets.fcose
    const layoutOpts = options.disableAnimations?.value
      ? { ...baseLayout, animate: false }
      : tuneLayout(baseLayout, nodeCount)

    cy.value = cytoscape({
      container: container.value,
      elements,
      style: createGraphStylesheet(),
      layout: layoutOpts,
      minZoom: 0.1,
      maxZoom: 4,
      wheelSensitivity: getWheelSensitivity(nodeCount),
      boxSelectionEnabled: false,
    })

    // Update label colors for legend after styles are applied
    nextTick(() => {
      labelColors.value = getLabelColors()
    })

    // Watch for container resizes and re-fit the graph
    resizeObserver?.disconnect()
    resizeObserver = new ResizeObserver(() => {
      cy.value?.resize()
      cy.value?.fit(undefined, 40)
    })
    resizeObserver.observe(container.value)

    // Performance: hide labels on large graphs until zoomed in
    if (nodeCount > 200) {
      cy.value.nodes().addClass('hide-label')
      cy.value.on('zoom', () => {
        const zoom = cy.value?.zoom() ?? 1
        if (zoom > 1.2) {
          cy.value?.nodes().removeClass('hide-label')
        } else {
          cy.value?.nodes().addClass('hide-label')
        }
      })
    }

    // ── Interactions ──────────────────────────────────────────────────────

    // Click node → select it
    cy.value.on('tap', 'node', (evt) => {
      cy.value?.nodes().removeClass('selected')
      evt.target.addClass('selected')
      const d = evt.target.data()
      selectedNode.value = {
        id: d.id,
        label: d.label,
        displayName: d.displayName,
        properties: d._properties ?? {},
      }
    })

    // Click background → deselect
    cy.value.on('tap', (evt) => {
      if (evt.target === cy.value) {
        cy.value?.nodes().removeClass('selected')
        selectedNode.value = null
      }
    })

    // Hover node → highlight neighborhood
    cy.value.on('mouseover', 'node', (evt) => {
      const node = evt.target
      hoveredNodeId.value = node.id()
      node.addClass('hover')
      node.connectedEdges().addClass('hover')
      node.neighborhood('node').addClass('neighbor')
    })

    cy.value.on('mouseout', 'node', () => {
      hoveredNodeId.value = null
      cy.value?.elements().removeClass('hover neighbor')
    })

    // Double-click → center + zoom
    cy.value.on('dbltap', 'node', (evt) => {
      cy.value?.animate({
        center: { eles: evt.target },
        zoom: 2.5,
        duration: 300,
      } as any)
    })
  }

  /** Fit the entire graph into the viewport. */
  function zoomToFit() {
    cy.value?.animate({
      fit: { padding: 40 } as any,
      duration: 300,
    } as any)
  }

  /** Search for nodes by displayName substring. */
  function searchNode(query: string) {
    if (!cy.value || !query.trim()) {
      clearSearch()
      return
    }
    const q = query.toLowerCase()
    const matches = cy.value.nodes().filter((n) => {
      const name = String(n.data('displayName') ?? '').toLowerCase()
      const id = String(n.data('id') ?? '').toLowerCase()
      return name.includes(q) || id.includes(q)
    })

    cy.value.elements().removeClass('search-match search-dim')

    if (matches.length > 0) {
      matches.addClass('search-match')
      cy.value.elements().not(matches).not(matches.connectedEdges()).addClass('search-dim')
      cy.value.animate({
        center: { eles: matches.first() },
        duration: 300,
      } as any)
    }
  }

  /** Clear search highlighting. */
  function clearSearch() {
    cy.value?.elements().removeClass('search-match search-dim')
  }

  /** Change the layout algorithm. */
  function changeLayout(name: string) {
    if (!cy.value || !graphData.value) return
    const baseLayout = layoutPresets[name] ?? layoutPresets.fcose
    const layoutOpts = options.disableAnimations?.value
      ? { ...baseLayout, animate: false }
      : tuneLayout(baseLayout, graphData.value.nodes.length)

    const layout = cy.value.layout(layoutOpts)
    layout.run()
  }

  /** Toggle visibility of a node label group. */
  function toggleLabel(label: string, visible: boolean) {
    if (!cy.value) return
    const nodes = cy.value.nodes(`[label = "${label}"]`)
    if (visible) {
      nodes.removeClass('label-hidden')
      nodes.connectedEdges().removeClass('label-hidden')
    } else {
      nodes.addClass('label-hidden')
      nodes.connectedEdges().addClass('label-hidden')
    }
  }

  // Re-initialize when data changes
  watch(graphData, () => {
    selectedNode.value = null
    hoveredNodeId.value = null
    nextTick(initialize)
  })

  // Initialize on mount when container becomes available
  watch(container, (el) => {
    if (el && graphData.value) {
      nextTick(initialize)
    }
  })

  onBeforeUnmount(() => {
    resizeObserver?.disconnect()
    resizeObserver = null
    cy.value?.destroy()
    cy.value = null
  })

  return {
    cy,
    selectedNode,
    hoveredNodeId,
    labelColors,
    zoomToFit,
    searchNode,
    clearSearch,
    changeLayout,
    toggleLabel,
  }
}
