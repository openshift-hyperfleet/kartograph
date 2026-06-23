import { describe, expect, it } from 'vitest'
import { streamExtractionChatTurn, streamRuntimeWarmup } from '../utils/kgExtractionChat'

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

  it('targets the proactive runtime warmup NDJSON endpoint with UI mode in body', async () => {
    const originalFetch = globalThis.fetch
    const calls: Array<{ url: string; init?: RequestInit }> = []
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), init })
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              '{"type":"ready","runtime_base_url":"http://runtime:8787"}\n{"type":"done","ok":true,"ready":true}\n',
            ),
          )
          controller.close()
        },
      })
      return new Response(body, { status: 200, headers: { 'Content-Type': 'application/x-ndjson' } })
    }) as typeof fetch

    try {
      const events = []
      for await (const event of streamRuntimeWarmup({
        apiBaseUrl: 'http://api.test',
        accessToken: 'token',
        tenantId: 'tenant-1',
        kgId: 'kg-1',
        sessionMode: 'schema_bootstrap',
        uiMode: 'initial-schema-design',
      })) {
        events.push(event)
      }

      expect(events).toEqual([
        { type: 'ready', runtime_base_url: 'http://runtime:8787' },
        { type: 'done', ok: true, ready: true },
      ])
      expect(calls[0]?.url).toContain(
        '/extraction/knowledge-graphs/kg-1/sessions/schema_bootstrap/runtime/warm',
      )
      expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({
        graph_management_ui_mode: 'initial-schema-design',
      })
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  it('throws when the NDJSON stream ends without a terminal done event', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = (async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode('{"type":"thinking","recent":["Still working…"]}\n'),
          )
          controller.close()
        },
      })
      return new Response(body, { status: 200, headers: { 'Content-Type': 'application/x-ndjson' } })
    }) as typeof fetch

    try {
      const iterator = streamExtractionChatTurn({
        apiBaseUrl: 'http://api.test',
        accessToken: 'token',
        tenantId: 'tenant-1',
        kgId: 'kg-1',
        sessionMode: 'schema_bootstrap',
        uiMode: 'initial-schema-design',
        message: 'Hello',
      })

      await expect(async () => {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        for await (const _event of iterator) {
          // drain stream
        }
      }).rejects.toThrow('stream ended before completion')
    } finally {
      globalThis.fetch = originalFetch
    }
  })
})
