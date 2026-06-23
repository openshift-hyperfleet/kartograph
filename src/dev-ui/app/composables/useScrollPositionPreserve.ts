import { nextTick } from 'vue'

export type ScrollSnapshot = Map<HTMLElement, number>

/** Capture scrollTop for each non-null element. */
export function captureScrollPositions(elements: Array<HTMLElement | null | undefined>): ScrollSnapshot {
  const snapshot = new Map<HTMLElement, number>()
  for (const el of elements) {
    if (el) snapshot.set(el, el.scrollTop)
  }
  return snapshot
}

/** Restore scrollTop from a prior capture (double rAF for layout-settled DOM). */
export function restoreScrollPositions(snapshot: ScrollSnapshot): void {
  void nextTick(() => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        for (const [el, top] of snapshot) {
          if (el.isConnected) el.scrollTop = top
        }
      })
    })
  })
}

/** Run async work without changing scroll positions on the given elements. */
export async function withPreservedScrollPositions<T>(
  elements: Array<HTMLElement | null | undefined>,
  fn: () => Promise<T>,
): Promise<T> {
  const snapshot = captureScrollPositions(elements)
  try {
    return await fn()
  } finally {
    restoreScrollPositions(snapshot)
  }
}

/** True when the user is within `thresholdPx` of the bottom of a scroll container. */
export function isScrollNearBottom(element: HTMLElement, thresholdPx = 48): boolean {
  const distance = element.scrollHeight - element.scrollTop - element.clientHeight
  return distance <= thresholdPx
}
