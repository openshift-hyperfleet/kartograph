export const layoutPresets: Record<string, any> = {
  fcose: {
    name: 'fcose',
    quality: 'proof',
    randomize: true,
    animate: true,
    animationDuration: 600,
    fit: true,
    padding: 60,
    nodeDimensionsIncludeLabels: true,
    nodeRepulsion: 8000,
    idealEdgeLength: 100,
    edgeElasticity: 0.45,
    nestingFactor: 0.1,
    gravity: 0.1,
    gravityRange: 2.0,
    numIter: 2500,
    nodeSeparation: 120,
    tile: true,
    tilingPaddingVertical: 30,
    tilingPaddingHorizontal: 40,
  },
  breadthfirst: {
    name: 'breadthfirst',
    directed: true,
    spacingFactor: 1.25,
    animate: true,
    animationDuration: 400,
    fit: true,
    padding: 60,
  },
  concentric: {
    name: 'concentric',
    animate: true,
    animationDuration: 400,
    fit: true,
    padding: 60,
    concentric: (node: any) => node.degree(),
    levelWidth: () => 2,
  },
  grid: {
    name: 'grid',
    animate: true,
    animationDuration: 400,
    fit: true,
    padding: 60,
    avoidOverlap: true,
    avoidOverlapPadding: 40,
    nodeDimensionsIncludeLabels: true,
    condense: false,
  },
  circle: {
    name: 'circle',
    animate: true,
    animationDuration: 400,
    fit: true,
    padding: 60,
  },
  'cise-label': {
    name: 'cise',
    animate: 'end',
    animationDuration: 500,
    fit: true,
    padding: 60,
    nodeDimensionsIncludeLabels: true,
    idealInterClusterEdgeLengthCoefficient: 1.6,
    allowNodesInsideCircle: false,
    nodeSeparation: 12,
    // clusters: injected at runtime by useCytoscape
  },
  'cise-mcl': {
    name: 'cise',
    animate: 'end',
    animationDuration: 500,
    fit: true,
    padding: 60,
    nodeDimensionsIncludeLabels: true,
    idealInterClusterEdgeLengthCoefficient: 1.4,
    allowNodesInsideCircle: false,
    nodeSeparation: 12,
    // clusters: injected at runtime by useCytoscape
  },
}

/**
 * Select the best layout for a given graph topology.
 * - 0 edges → grid (force-directed has no forces to direct)
 * - sparse (< 0.5 edges/node) → fcose with extra repulsion
 * - normal/dense → standard fcose
 */
export function selectDefaultLayout(nodeCount: number, edgeCount: number): string {
  if (edgeCount === 0) return 'grid'
  return 'fcose'
}

/** Apply performance tuning to layout options based on node count. */
export function tuneLayout(preset: Record<string, any>, nodeCount: number): Record<string, any> {
  const tuned = { ...preset }

  if (nodeCount > 200) {
    tuned.animate = false
  }

  if (nodeCount > 500 && tuned.name === 'fcose') {
    tuned.quality = 'draft'
    tuned.numIter = 1000
  }

  return tuned
}
