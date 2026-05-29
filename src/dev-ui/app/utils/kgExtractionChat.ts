/** Stream graph-management chat turns over NDJSON. */

import type { GraphManagementMode } from '@/utils/kgGraphManagement'

export interface ExtractionChatStreamEvent {
  type: 'thinking' | 'wait' | 'done'
  recent?: string[]
  phase?: string
  message?: string
  ok?: boolean
  reply?: string | null
  wait?: boolean
  error?: { code: string; message: string }
}

export interface StreamExtractionChatOptions {
  apiBaseUrl: string
  accessToken: string | null
  tenantId: string | null
  kgId: string
  sessionMode: 'schema_bootstrap' | 'extraction_operations'
  uiMode: GraphManagementMode
  message: string
}

export async function* streamExtractionChatTurn(
  options: StreamExtractionChatOptions,
): AsyncGenerator<ExtractionChatStreamEvent> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/x-ndjson',
  }
  if (options.accessToken) {
    headers.Authorization = `Bearer ${options.accessToken}`
  }
  if (options.tenantId) {
    headers['X-Tenant-ID'] = options.tenantId
  }

  const response = await fetch(
    `${options.apiBaseUrl}/extraction/knowledge-graphs/${encodeURIComponent(options.kgId)}/sessions/${options.sessionMode}/chat`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({
        message: options.message,
        graph_management_ui_mode: options.uiMode,
      }),
    },
  )

  if (!response.ok) {
    const body = await response.text().catch(() => '')
    throw new Error(body || `${response.status} ${response.statusText}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('No response body from Graph Management Assistant')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n')
    buffer = parts.pop() ?? ''
    for (const line of parts) {
      const trimmed = line.trim()
      if (!trimmed) continue
      yield JSON.parse(trimmed) as ExtractionChatStreamEvent
    }
  }

  const tail = buffer.trim()
  if (tail) {
    yield JSON.parse(tail) as ExtractionChatStreamEvent
  }
}
