import type { CypherResult } from '~/types'

/**
 * Typed API client for the Querying bounded context.
 *
 * The production MCP server uses the Streamable HTTP transport (JSON-RPC
 * over `POST /query/mcp`). This transport requires the client to accept
 * both `application/json` and `text/event-stream`, because the server may
 * respond with either content type.
 *
 * We use native `fetch()` instead of `$fetch` so we can inspect the
 * response `Content-Type` and handle SSE streams when necessary.
 */
export function useQueryApi() {
  const config = useRuntimeConfig()
  const { accessToken } = useAuth()
  const currentTenantId = useState<string | null>('tenant:current', () => null)

  /**
   * Execute a Cypher query against the knowledge graph via the MCP
   * `query_graph` tool.
   *
   * Under the hood this sends a JSON-RPC `tools/call` request to the
   * MCP streamable HTTP endpoint.
   */
  async function queryGraph(
    cypher: string,
    timeoutSeconds?: number,
    maxRows?: number,
  ): Promise<CypherResult> {
    const baseUrl = config.public.apiBaseUrl as string
    const mcpUrl = `${baseUrl}/query/mcp`

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'application/json, text/event-stream',
    }

    if (accessToken.value) {
      headers['Authorization'] = `Bearer ${accessToken.value}`
    }

    if (currentTenantId.value) {
      headers['X-Tenant-ID'] = currentTenantId.value
    }

    const args: Record<string, unknown> = { cypher }
    if (timeoutSeconds !== undefined) args.timeout_seconds = timeoutSeconds
    if (maxRows !== undefined) args.max_rows = maxRows

    // JSON-RPC 2.0 request calling the MCP `query_graph` tool.
    // For stateless_http=True servers we can skip the initialize
    // handshake and call tools/call directly.
    const rpcRequest = {
      jsonrpc: '2.0' as const,
      id: crypto.randomUUID(),
      method: 'tools/call',
      params: {
        name: 'query_graph',
        arguments: args,
      },
    }

    const response = await fetch(mcpUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify(rpcRequest),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`MCP request failed (${response.status}): ${errorText}`)
    }

    const contentType = response.headers.get('content-type') || ''

    let rpcResponse: {
      jsonrpc: string
      id: string
      result?: { content: Array<{ type: string; text: string }> }
      error?: { code: number; message: string }
    }

    if (contentType.includes('text/event-stream')) {
      rpcResponse = await parseSSEResponse(response)
    } else {
      rpcResponse = await response.json()
    }

    if (rpcResponse.error) {
      throw new Error(`MCP error ${rpcResponse.error.code}: ${rpcResponse.error.message}`)
    }

    // The query_graph tool returns results as a JSON text content block
    const textContent = rpcResponse.result?.content?.find((c) => c.type === 'text')
    if (!textContent) {
      return { rows: [], row_count: 0 }
    }

    // The tool returns a dict with success, rows, row_count, etc.
    const toolResult = JSON.parse(textContent.text)

    if (toolResult.success === false) {
      throw new Error(toolResult.message || 'Query failed')
    }

    return {
      rows: toolResult.rows || [],
      row_count: toolResult.row_count || 0,
    }
  }

  return {
    queryGraph,
  }
}

/**
 * Parse an SSE (Server-Sent Events) response body to extract the last
 * JSON-RPC message payload.
 *
 * The stream contains events like:
 * ```
 * event: message
 * data: {"jsonrpc":"2.0","id":"...","result":{...}}
 * ```
 */
async function parseSSEResponse(response: Response): Promise<any> {
  const text = await response.text()
  const lines = text.split('\n')

  let lastData = ''
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      lastData = line.slice(6)
    }
  }

  if (!lastData) {
    throw new Error('No data received in SSE response')
  }

  return JSON.parse(lastData)
}
