import type { CypherResult } from '~/types'

/**
 * Typed API client for the Querying bounded context.
 *
 * The production MCP server uses streamable HTTP (JSON-RPC over
 * `POST /query/mcp`). For the dev UI we call the `query_graph` MCP tool
 * via a JSON-RPC request to the MCP endpoint.
 *
 * NOTE: Full MCP client integration (tool discovery, SSE streams, etc.)
 * will be wired up in a future iteration. The interface below is stable.
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
      'Accept': 'application/json',
    }

    if (accessToken.value) {
      headers['Authorization'] = `Bearer ${accessToken.value}`
    }

    if (currentTenantId.value) {
      headers['X-Tenant-ID'] = currentTenantId.value
    }

    const args: Record<string, unknown> = { query: cypher }
    if (timeoutSeconds !== undefined) args.timeout_seconds = timeoutSeconds
    if (maxRows !== undefined) args.max_rows = maxRows

    // JSON-RPC 2.0 request calling the MCP `query_graph` tool
    const rpcRequest = {
      jsonrpc: '2.0',
      id: crypto.randomUUID(),
      method: 'tools/call',
      params: {
        name: 'query_graph',
        arguments: args,
      },
    }

    const response = await $fetch<{
      jsonrpc: string
      id: string
      result?: {
        content: Array<{ type: string; text: string }>
      }
      error?: { code: number; message: string }
    }>(mcpUrl, {
      method: 'POST',
      headers,
      body: rpcRequest,
    })

    if (response.error) {
      throw new Error(`MCP error ${response.error.code}: ${response.error.message}`)
    }

    // The query_graph tool returns results as a JSON text content block
    const textContent = response.result?.content?.find((c) => c.type === 'text')
    if (!textContent) {
      return { rows: [], row_count: 0 }
    }

    return JSON.parse(textContent.text) as CypherResult
  }

  return {
    queryGraph,
  }
}
