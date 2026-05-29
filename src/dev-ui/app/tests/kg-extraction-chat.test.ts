import { describe, expect, it } from 'vitest'
import { streamExtractionChatTurn } from '../utils/kgExtractionChat'

describe('kgExtractionChat', () => {
  it('targets the extraction chat NDJSON endpoint with UI mode in body', async () => {
    const originalFetch = globalThis.fetch
    const calls: Array<{ url: string; init?: RequestInit }> = []
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), init })
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('{"type":"done","ok":true,"reply":"hi"}\n'))
          controller.close()
        },
      })
      return new Response(body, { status: 200, headers: { 'Content-Type': 'application/x-ndjson' } })
    }) as typeof fetch

    try {
      const events = []
      for await (const event of streamExtractionChatTurn({
        apiBaseUrl: 'http://api.test',
        accessToken: 'token',
        tenantId: 'tenant-1',
        kgId: 'kg-1',
        sessionMode: 'schema_bootstrap',
        uiMode: 'initial-schema-design',
        message: 'Hello',
      })) {
        events.push(event)
      }

      expect(events).toEqual([{ type: 'done', ok: true, reply: 'hi' }])
      expect(calls[0]?.url).toContain('/extraction/knowledge-graphs/kg-1/sessions/schema_bootstrap/chat')
      expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({
        message: 'Hello',
        graph_management_ui_mode: 'initial-schema-design',
      })
    } finally {
      globalThis.fetch = originalFetch
    }
  })
})
