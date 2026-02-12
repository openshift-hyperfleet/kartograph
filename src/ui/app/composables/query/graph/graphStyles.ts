import type { Stylesheet } from 'cytoscape'

// 12 distinct colors for node labels, assigned deterministically
const PALETTE = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
  '#14b8a6', '#e11d48',
]

const labelColorMap = new Map<string, string>()
let nextColorIndex = 0

/** Get a deterministic color for a node label. */
export function colorForLabel(label: string): string {
  let color = labelColorMap.get(label)
  if (!color) {
    color = PALETTE[nextColorIndex % PALETTE.length]
    labelColorMap.set(label, color)
    nextColorIndex++
  }
  return color
}

/** Reset the color mapping (useful when switching between results). */
export function resetLabelColors(): void {
  labelColorMap.clear()
  nextColorIndex = 0
}

/** Get the current label → color mapping for the legend. */
export function getLabelColors(): Map<string, string> {
  return new Map(labelColorMap)
}

export const graphStylesheet: Stylesheet[] = [
  {
    selector: 'node',
    style: {
      'background-color': (ele: any) => colorForLabel(ele.data('label')),
      'label': 'data(displayName)',
      'color': '#f1f5f9',
      'text-valign': 'center',
      'text-halign': 'center',
      'font-size': '10px',
      'font-family': 'ui-monospace, SFMono-Regular, monospace',
      'text-max-width': '90px',
      'text-wrap': 'ellipsis',
      'width': 36,
      'height': 36,
      'border-width': 2,
      'border-color': '#334155',
      'text-outline-width': 2,
      'text-outline-color': '#0f172a',
      'transition-property': 'border-color, border-width, opacity',
      'transition-duration': '150ms',
    } as any,
  },
  {
    selector: 'edge',
    style: {
      'width': 1.5,
      'line-color': '#475569',
      'target-arrow-color': '#475569',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'arrow-scale': 0.8,
      'transition-property': 'width, line-color, opacity',
      'transition-duration': '150ms',
    } as any,
  },
  // Hover state
  {
    selector: 'node.hover',
    style: {
      'border-color': '#f8fafc',
      'border-width': 3,
      'z-index': 10,
    } as any,
  },
  {
    selector: 'edge.hover',
    style: {
      'width': 3,
      'line-color': '#94a3b8',
      'target-arrow-color': '#94a3b8',
      'label': 'data(label)',
      'font-size': '9px',
      'color': '#e2e8f0',
      'text-rotation': 'autorotate',
      'text-outline-width': 2,
      'text-outline-color': '#0f172a',
    } as any,
  },
  {
    selector: 'node.neighbor',
    style: {
      'border-color': '#64748b',
      'border-width': 3,
    } as any,
  },
  // Selected node
  {
    selector: 'node.selected',
    style: {
      'border-color': '#fbbf24',
      'border-width': 4,
      'z-index': 20,
    } as any,
  },
  // Search match
  {
    selector: 'node.search-match',
    style: {
      'border-color': '#fbbf24',
      'border-width': 4,
      'z-index': 20,
    } as any,
  },
  {
    selector: '.search-dim',
    style: {
      'opacity': 0.15,
    } as any,
  },
  // Hidden by filter
  {
    selector: '.label-hidden',
    style: {
      'display': 'none',
    } as any,
  },
  // Large graph: hide labels until zoomed
  {
    selector: 'node.hide-label',
    style: {
      'label': '',
    } as any,
  },
]
