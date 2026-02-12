export const layoutPresets: Record<string, any> = {
  fcose: {
    name: 'fcose',
    quality: 'default',
    randomize: true,
    animate: true,
    animationDuration: 600,
    fit: true,
    padding: 40,
    nodeRepulsion: 4500,
    idealEdgeLength: 80,
    edgeElasticity: 0.45,
    nestingFactor: 0.1,
    gravity: 0.25,
    numIter: 2500,
  },
  breadthfirst: {
    name: 'breadthfirst',
    directed: true,
    spacingFactor: 1.25,
    animate: true,
    animationDuration: 400,
    fit: true,
    padding: 40,
  },
  concentric: {
    name: 'concentric',
    animate: true,
    animationDuration: 400,
    fit: true,
    padding: 40,
    concentric: (node: any) => node.degree(),
    levelWidth: () => 2,
  },
  grid: {
    name: 'grid',
    animate: true,
    animationDuration: 400,
    fit: true,
    padding: 40,
  },
  circle: {
    name: 'circle',
    animate: true,
    animationDuration: 400,
    fit: true,
    padding: 40,
  },
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
