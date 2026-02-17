import type { Stylesheet } from 'cytoscape'

// 12 distinct colors for node labels, assigned deterministically
const PALETTE = [
  '#ee0000', '#37a3a3', '#5e40be', '#f5921b', '#63993d',
  '#0066cc', '#f0561d', '#ffcc17', '#a60000', '#f56e6e',
  '#b1380b', '#4394e5',
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

/** Read a CSS custom property value from the document root, with a fallback. */
function getCssColor(varName: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback
  const val = getComputedStyle(document.documentElement).getPropertyValue(varName).trim()
  return val || fallback
}

/** Resolve all theme colors once and return a cached object for use in stylesheets. */
function resolveThemeColors() {
  return {
    foreground: getCssColor('--foreground', '#f1f5f9'),
    background: getCssColor('--background', '#0f172a'),
    border: getCssColor('--border', '#334155'),
    mutedForeground: getCssColor('--muted-foreground', '#475569'),
    accentForeground: getCssColor('--accent-foreground', '#f8fafc'),
    ring: getCssColor('--ring', '#64748b'),
  }
}

/** Build the Cytoscape stylesheet with colors resolved from CSS variables. */
export function createGraphStylesheet(): Stylesheet[] {
  const theme = resolveThemeColors()

  return [
    {
      selector: 'node',
      style: {
        'background-color': (ele: any) => colorForLabel(ele.data('label')),
        'label': 'data(displayName)',
        'color': '#f8fafc',
        'text-valign': 'bottom',
        'text-halign': 'center',
        'text-margin-y': 6,
        'font-size': '9px',
        'font-family': 'ui-monospace, SFMono-Regular, monospace',
        'text-max-width': '80px',
        'text-wrap': 'ellipsis',
        'width': 36,
        'height': 36,
        'border-width': 2,
        'border-color': theme.border,
        'text-outline-width': 1.5,
        'text-outline-color': 'rgba(0, 0, 0, 0.6)',
        'transition-property': 'border-color, border-width, opacity',
        'transition-duration': '150ms',
      } as any,
    },
    {
      selector: 'edge',
      style: {
        'width': 1.5,
        'line-color': theme.mutedForeground,
        'target-arrow-color': theme.mutedForeground,
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
        'border-color': theme.accentForeground,
        'border-width': 3,
        'z-index': 10,
      } as any,
    },
    {
      selector: 'edge.hover',
      style: {
        'width': 3,
        'line-color': theme.ring,
        'target-arrow-color': theme.ring,
        'label': 'data(label)',
        'font-size': '9px',
        'color': '#f8fafc',
        'text-rotation': 'autorotate',
        'text-outline-width': 3,
        'text-outline-color': 'rgba(0, 0, 0, 0.7)',
      } as any,
    },
    {
      selector: 'node.neighbor',
      style: {
        'border-color': theme.ring,
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
    // Expanded node indicator (thicker double border)
    {
      selector: 'node.expanded',
      style: {
        'border-width': 3,
        'border-style': 'double',
      } as any,
    },
    // Loading state while fetching neighbors
    {
      selector: 'node.expanding',
      style: {
        'border-width': 3,
        'border-color': '#fbbf24',
        'border-style': 'dashed',
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
}
