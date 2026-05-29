/** Stream graph-management chat turns and proactive runtime warmup over NDJSON. */

import type { GraphManagementMode } from '@/utils/kgGraphManagement'

export interface ExtractionChatStreamEvent {
  type: 'thinking' | 'wait' | 'ready' | 'done'
  recent?: string[]
  phase?: string
  message?: string
  runtime_base_url?: string
  ok?: boolean
  reply?: string | null
  ready?: boolean
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

export interface StreamRuntimeWarmupOptions {
  apiBaseUrl: string
  accessToken: string | null
  tenantId: string | null
  kgId: string
  sessionMode: 'schema_bootstrap' | 'extraction_operations'
  uiMode: GraphManagementMode
}

async function* streamNdjsonPost(
  url: string,
  headers: Record<string, string>,
  body: Record<string, unknown>,
): AsyncGenerator<ExtractionChatStreamEvent> {
  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(text || `${response.status} ${response.statusText}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('No response body from Graph Management Assistant')
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let sawTerminalDone = false

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n')
    buffer = parts.pop() ?? ''
    for (const line of parts) {
      const trimmed = line.trim()
      if (!trimmed) continue
      const event = JSON.parse(trimmed) as ExtractionChatStreamEvent
      if (event.type === 'done') {
        sawTerminalDone = true
      }
      yield event
    }
  }

  const tail = buffer.trim()
  if (tail) {
    const event = JSON.parse(tail) as ExtractionChatStreamEvent
    if (event.type === 'done') {
      sawTerminalDone = true
    }
    yield event
  }

  if (!sawTerminalDone) {
    throw new Error('Graph Management Assistant stream ended before completion.')
  }
}

function buildExtractionHeaders(
  accessToken: string | null,
  tenantId: string | null,
): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/x-ndjson',
  }
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`
  }
  if (tenantId) {
    headers['X-Tenant-ID'] = tenantId
  }
  return headers
}

export async function* streamRuntimeWarmup(
  options: StreamRuntimeWarmupOptions,
): AsyncGenerator<ExtractionChatStreamEvent> {
  const headers = buildExtractionHeaders(options.accessToken, options.tenantId)
  const url = `${options.apiBaseUrl}/extraction/knowledge-graphs/${encodeURIComponent(options.kgId)}/sessions/${options.sessionMode}/runtime/warm`
  yield* streamNdjsonPost(url, headers, {
    graph_management_ui_mode: options.uiMode,
  })
}

export async function* streamExtractionChatTurn(
  options: StreamExtractionChatOptions,
): AsyncGenerator<ExtractionChatStreamEvent> {
  const headers = buildExtractionHeaders(options.accessToken, options.tenantId)
  const url = `${options.apiBaseUrl}/extraction/knowledge-graphs/${encodeURIComponent(options.kgId)}/sessions/${options.sessionMode}/chat`
  yield* streamNdjsonPost(url, headers, {
    message: options.message,
    graph_management_ui_mode: options.uiMode,
  })
}
