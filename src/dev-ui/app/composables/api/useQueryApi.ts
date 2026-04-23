import type { CypherResult } from '~/types'

interface JsonRpcResponse {
  jsonrpc: string
  id: string
  result?: { content: Array<{ type: string; text: string }> }
  error?: { code: number; message: string }
}

/**
 * Build the `arguments` object for the MCP `query_graph` tool call.
 *
 * Extracted as a pure function so it can be unit-tested independently of
 * the composable and so that the query console page can reuse the same
 * argument-construction logic regardless of how it obtains the parameters.
 *
 * @param cypher - The Cypher query string to execute.
 * @param timeoutSeconds - Maximum query execution time in seconds.
 * @param maxRows - Maximum number of rows to return.
 * @param knowledgeGraphId - Optional knowledge graph ID to scope the query.
 *   When provided, the query is restricted to data within that graph.
 *   When omitted (or `undefined`), the query spans all knowledge graphs
 *   accessible to the caller in the current tenant.
 * @returns An argument record ready to pass as `params.arguments` in the
 *   JSON-RPC `tools/call` request.
 */
export function buildQueryGraphArgs(
  cypher: string,
  timeoutSeconds: number,
  maxRows: number,
  knowledgeGraphId?: string,
): Record<string, unknown> {
  const args: Record<string, unknown> = {
    cypher,
    timeout_seconds: timeoutSeconds,
    max_rows: maxRows,
  }
  if (knowledgeGraphId) {
    args.knowledge_graph_id = knowledgeGraphId
  }
  return args
}

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
   *
   * @param cypher - The Cypher query to run.
   * @param timeoutSeconds - Query timeout in seconds (default 30).
   * @param maxRows - Maximum rows to return (default 1000).
   * @param knowledgeGraphId - Optional knowledge graph to scope the query.
   */
  async function queryGraph(
    cypher: string,
    timeoutSeconds?: number,
    maxRows?: number,
    knowledgeGraphId?: string,
  ): Promise<CypherResult> {
    const mcpUrl = config.public.mcpEndpointUrl as string

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

    const args = buildQueryGraphArgs(
      cypher,
      timeoutSeconds ?? 30,
      maxRows ?? 1000,
      knowledgeGraphId,
    )

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

    let rpcResponse: JsonRpcResponse

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
async function parseSSEResponse(response: Response): Promise<JsonRpcResponse> {
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
