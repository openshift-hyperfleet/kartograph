import { shallowRef, ref, watch, onBeforeUnmount, nextTick, type Ref } from 'vue'
import cytoscape from 'cytoscape'
import fcose from 'cytoscape-fcose'
// @ts-ignore -- cytoscape-cise has no TypeScript declarations
import cise from 'cytoscape-cise'
import type { GraphData, GraphNode, GraphEdge } from '~/types'
import { createGraphStylesheet, resetLabelColors, getLabelColors } from './graphStyles'
import { layoutPresets, tuneLayout, selectDefaultLayout } from './graphLayouts'
import { clusterByLabel, clusterByTopology } from './useClustering'

// Register layout extensions once at module level
let fcoseRegistered = false
if (!fcoseRegistered) {
  cytoscape.use(fcose)
  fcoseRegistered = true
}

let ciseRegistered = false
if (!ciseRegistered) {
  cytoscape.use(cise)
  ciseRegistered = true
}

/** Scale wheel sensitivity based on graph size to balance responsiveness and control. */
function getWheelSensitivity(nodeCount: number): number {
  if (nodeCount < 50) return 1.0
  if (nodeCount <= 200) return 0.8
  if (nodeCount <= 500) return 0.6
  return 0.4
}

/** Maximum node count beyond which expand is blocked to protect performance. */
const MAX_NODES_FOR_EXPAND = 1000

export function useCytoscape(
  container: Ref<HTMLElement | null>,
  graphData: Ref<GraphData | null>,
  options: {
    layout?: Ref<string>
    disableAnimations?: Ref<boolean>
    onExpandNode?: (nodeId: string) => Promise<{ nodes: GraphNode[]; edges: GraphEdge[] } | null>
  } = {},
) {
  const cy = shallowRef<cytoscape.Core | null>(null)
  const selectedNode = ref<GraphNode | null>(null)
  const hoveredNodeId = ref<string | null>(null)
  const labelColors = ref<Map<string, string>>(new Map())
  const expandedNodes = ref<Set<string>>(new Set())
  const expandingNode = ref<string | null>(null)
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

    const edgeCount = data.edges.length
    // Use the user's chosen layout, or auto-select based on graph topology
    const layoutName = options.layout?.value ?? selectDefaultLayout(nodeCount, edgeCount)
    const baseLayout = layoutPresets[layoutName] ?? layoutPresets.fcose
    let layoutOpts = options.disableAnimations?.value
      ? { ...baseLayout, animate: false }
      : tuneLayout(baseLayout, nodeCount)

    // CiSE layouts need a live cy instance to compute clusters, so we
    // create the instance with a preset layout first and run CiSE after.
    const needsDeferredCise = layoutName === 'cise-label' || layoutName === 'cise-mcl'

    cy.value = cytoscape({
      container: container.value,
      elements,
      style: createGraphStylesheet(),
      layout: needsDeferredCise ? { name: 'preset' } : layoutOpts,
      minZoom: 0.1,
      maxZoom: 4,
      wheelSensitivity: getWheelSensitivity(nodeCount),
      boxSelectionEnabled: false,
    })

    // Run deferred CiSE layout now that the cy instance exists
    if (needsDeferredCise && cy.value) {
      if (layoutName === 'cise-label') {
        layoutOpts = { ...layoutOpts, clusters: clusterByLabel(cy.value) }
      } else {
        layoutOpts = { ...layoutOpts, clusters: clusterByTopology(cy.value) }
      }
      cy.value.layout(layoutOpts).run()
    }

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

    // Double-click → expand / contract neighbors
    cy.value.on('dbltap', 'node', async (evt) => {
      const nodeId = evt.target.id()

      if (expandedNodes.value.has(nodeId)) {
        contractNode(nodeId)
      } else {
        await expandNode(nodeId)
      }
    })
  }

  // ── Expand / Contract ──────────────────────────────────────────────────

  async function expandNode(nodeId: string) {
    if (!cy.value || !options.onExpandNode || expandingNode.value) return

    // Guard: block expansion on very large graphs
    if (cy.value.nodes().length >= MAX_NODES_FOR_EXPAND) {
      console.warn(`Graph has ${cy.value.nodes().length} nodes – expand blocked for performance.`)
      return
    }

    expandingNode.value = nodeId
    cy.value.$id(nodeId).addClass('expanding')

    try {
      // Resolve application-level ID from properties when available
      const nodeData = cy.value.$id(nodeId).data()
      const apiId = (nodeData._properties?.id as string) || nodeId

      const result = await options.onExpandNode(apiId)
      if (!result || !cy.value) return

      const existingNodeIds = new Set(cy.value.nodes().map((n: cytoscape.NodeSingular) => n.id()))
      const existingEdgeIds = new Set(cy.value.edges().map((e: cytoscape.EdgeSingular) => e.id()))

      const newElements: cytoscape.ElementDefinition[] = []

      for (const node of result.nodes) {
        if (!existingNodeIds.has(node.id)) {
          newElements.push({
            group: 'nodes',
            data: {
              id: node.id,
              label: node.label,
              displayName: node.displayName,
              _properties: node.properties,
              _addedBy: nodeId,
            },
          })
        }
      }

      for (const edge of result.edges) {
        if (!existingEdgeIds.has(edge.id)) {
          const sourceExists = existingNodeIds.has(edge.source) || result.nodes.some(n => n.id === edge.source)
          const targetExists = existingNodeIds.has(edge.target) || result.nodes.some(n => n.id === edge.target)
          if (sourceExists && targetExists) {
            newElements.push({
              group: 'edges',
              data: {
                id: edge.id,
                source: edge.source,
                target: edge.target,
                label: edge.label,
                _properties: edge.properties,
              },
            })
          }
        }
      }

      if (newElements.length > 0) {
        const added = cy.value.add(newElements)

        // Position new nodes in a circle around the expanded node
        const expandedPos = cy.value.$id(nodeId).position()
        const newNodes = added.nodes()
        const count = newNodes.length
        newNodes.forEach((node: cytoscape.NodeSingular, i: number) => {
          const angle = (2 * Math.PI * i) / count
          const radius = 120
          node.position({
            x: expandedPos.x + radius * Math.cos(angle),
            y: expandedPos.y + radius * Math.sin(angle),
          })
        })

        // Run a local layout on the neighborhood so it settles nicely
        const neighborhood = cy.value.$id(nodeId).neighborhood().union(cy.value.$id(nodeId))
        neighborhood.layout({
          name: 'fcose',
          randomize: false,
          animate: true,
          animationDuration: 400,
          fit: false,
          nodeDimensionsIncludeLabels: true,
          nodeRepulsion: 4500,
          idealEdgeLength: 80,
        } as any).run()

        nextTick(() => {
          labelColors.value = getLabelColors()
        })
      }

      expandedNodes.value.add(nodeId)
      cy.value.$id(nodeId).addClass('expanded')
    } catch (err) {
      console.error('Failed to expand node:', err)
    } finally {
      expandingNode.value = null
      cy.value?.$id(nodeId).removeClass('expanding')
    }
  }

  function contractNode(nodeId: string) {
    if (!cy.value) return

    const addedByThis = cy.value.nodes().filter((n: cytoscape.NodeSingular) => n.data('_addedBy') === nodeId)

    // Only remove nodes that don't have other connections to pre-existing nodes
    // and haven't been expanded themselves
    const toRemove = addedByThis.filter((n: cytoscape.NodeSingular) => {
      const connectedToOthers = n.neighborhood('node').some((neighbor: cytoscape.NodeSingular) => {
        return neighbor.id() !== nodeId && !addedByThis.contains(neighbor)
      })
      const isExpanded = expandedNodes.value.has(n.id())
      return !connectedToOthers && !isExpanded
    })

    if (toRemove.length > 0) {
      cy.value.remove(toRemove)
    }

    expandedNodes.value.delete(nodeId)
    cy.value.$id(nodeId).removeClass('expanded')

    nextTick(() => {
      labelColors.value = getLabelColors()
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
    let layoutOpts = options.disableAnimations?.value
      ? { ...baseLayout, animate: false }
      : tuneLayout(baseLayout, graphData.value.nodes.length)

    // Inject clusters for CiSE layouts
    if (name === 'cise-label' && cy.value) {
      layoutOpts = { ...layoutOpts, clusters: clusterByLabel(cy.value) }
    } else if (name === 'cise-mcl' && cy.value) {
      layoutOpts = { ...layoutOpts, clusters: clusterByTopology(cy.value) }
    }

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
    expandedNodes.value = new Set()
    expandingNode.value = null
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
    expandedNodes,
    expandingNode,
    zoomToFit,
    searchNode,
    clearSearch,
    changeLayout,
    toggleLabel,
  }
}
