import type cytoscape from 'cytoscape'

/**
 * Group nodes by their `label` data attribute (node type).
 * Returns a 2D array of node ID arrays, one per cluster.
 */
export function clusterByLabel(cy: cytoscape.Core): string[][] {
  const groups = new Map<string, string[]>()
  cy.nodes().forEach((node) => {
    const label = node.data('label') || 'unknown'
    if (!groups.has(label)) groups.set(label, [])
    groups.get(label)!.push(node.id())
  })
  return Array.from(groups.values())
}

/**
 * Run Markov Clustering (MCL) on the graph to detect topological communities.
 * MCL is built into Cytoscape.js core — no extra dependency needed.
 * Returns a 2D array of node ID arrays, one per cluster.
 */
export function clusterByTopology(cy: cytoscape.Core, inflateFactor = 2): string[][] {
  const clusters = cy.elements().markovClustering({ attributes: [() => 1], inflateFactor })
  return clusters.map((cluster: any) => {
    return cluster.nodes().map((node: any) => node.id())
  })
}
