import { ref, onUnmounted } from 'vue'

// ── Types shared between worker and main thread ────────────────────────────

export interface LightParsedOperation {
  index: number
  op?: 'DEFINE' | 'CREATE' | 'UPDATE' | 'DELETE'
  type?: 'node' | 'edge'
  label?: string
  id?: string
  warnings: string[]
  lineStart: number
}

/** A single warning entry with enough context to locate and edit it */
export interface WorkerWarningEntry {
  opIndex: number
  op: string
  lineStart: number
  message: string
}

export interface WorkerParseResult {
  totalOps: number
  breakdown: { DEFINE: number; CREATE: number; UPDATE: number; DELETE: number; unknown: number }
  parseErrors: string[]
  previewOps: LightParsedOperation[]
  warningCount: number
  hasWarnings: boolean
  /** All collected warnings (capped at 1000) */
  warningEntries: WorkerWarningEntry[]
}

/** Content size threshold: above this, use the worker for parsing */
export const LARGE_FILE_THRESHOLD = 100_000 // 100KB

/**
 * Manages a Web Worker for off-thread JSONL parsing.
 *
 * For content below LARGE_FILE_THRESHOLD the caller should use synchronous
 * parsing — `requestParse()` returns `false` in that case.
 */
export function useMutationWorker() {
  const workerResult = ref<WorkerParseResult | null>(null)
  const parsing = ref(false)
  const parseTimeMs = ref(0)
  const isLargeFile = ref(false)

  let worker: Worker | null = null
  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let messageId = 0

  function getWorker(): Worker {
    if (!worker) {
      worker = new Worker(
        new URL('../workers/mutationParser.worker.ts', import.meta.url),
        { type: 'module' },
      )
      worker.onmessage = (e: MessageEvent) => {
        if (e.data.type === 'result' && e.data.id === messageId) {
          workerResult.value = e.data.result
          parseTimeMs.value = e.data.parseTimeMs
          parsing.value = false
        }
      }
    }
    return worker
  }

  /**
   * Request a parse. Debounces for large content.
   *
   * @returns `true` if the worker will handle parsing (large file),
   *          `false` if the caller should use synchronous parsing (small file).
   */
  function requestParse(content: string): boolean {
    const size = content.length
    isLargeFile.value = size > LARGE_FILE_THRESHOLD

    if (!isLargeFile.value) {
      // Small file: caller should use synchronous parsing
      workerResult.value = null
      parsing.value = false
      return false
    }

    // Large file: debounce and use worker
    if (debounceTimer) clearTimeout(debounceTimer)

    parsing.value = true
    const debounceMs = size > 10_000_000 ? 1000 : size > 1_000_000 ? 500 : 300

    debounceTimer = setTimeout(() => {
      messageId++
      getWorker().postMessage({ type: 'parse', content, id: messageId })
    }, debounceMs)

    return true
  }

  function terminate() {
    if (debounceTimer) clearTimeout(debounceTimer)
    if (worker) {
      worker.terminate()
      worker = null
    }
  }

  onUnmounted(terminate)

  return {
    workerResult,
    parsing,
    parseTimeMs,
    isLargeFile,
    requestParse,
    terminate,
  }
}
