/** Rolling thinking-line panel contract for Graph Management Assistant streams. */

export const THINKING_DISPLAY_LINE_COUNT = 3

export function normalizeThinkingActivityLines(
  lines: string[],
  slotCount: number = THINKING_DISPLAY_LINE_COUNT,
): string[] {
  const recent = lines.filter((line) => typeof line === 'string' && line.trim().length > 0)
  const tail = recent.slice(-slotCount)
  while (tail.length < slotCount) {
    tail.unshift('')
  }
  return tail
}

export function applyThinkingRecentUpdate(
  current: string[],
  recent: string[],
  slotCount: number = THINKING_DISPLAY_LINE_COUNT,
): string[] {
  if (recent.length === 0) {
    return normalizeThinkingActivityLines(current, slotCount)
  }
  return normalizeThinkingActivityLines(recent, slotCount)
}
