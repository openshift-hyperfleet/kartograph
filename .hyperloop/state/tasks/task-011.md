---
id: task-011
title: Add knowledge_graph_id filter and secure enclave to MCP query tool
spec_ref: specs/query/mcp-server.spec.md
status: not-started
phase: null
deps: [task-006]
round: 0
branch: null
pr: null
---

## What

Extend the `query_graph` MCP tool to accept an optional `knowledge_graph_id` parameter, and wire the secure enclave result redaction (implemented by task-006 in the graph layer) through the MCP query path.

## Spec gaps

**Optional KnowledgeGraph filter:**
> - GIVEN a `query_graph` call with an optional `knowledge_graph_id` parameter
> - WHEN the parameter is provided
> - THEN results are filtered to only that KnowledgeGraph

**Secure enclave redaction:**
> - GIVEN query results containing entities the caller is not authorized to view
> - WHEN the results are returned
> - THEN unauthorized nodes are redacted to ID-only (all other properties stripped)
> - AND unauthorized edges are redacted to ID, `start_id`, and `end_id` only
> - AND the graph topology is preserved

**Result truncation (minor):**
> - The server SHOULD fetch `limit + 1` rows and set `truncated` to true only if more than `limit` rows were available

## Current state

`query/presentation/mcp.py` — `query_graph()` has no `knowledge_graph_id` parameter. `MCPQueryService.execute_cypher_query()` passes results directly without secure enclave filtering.

The truncation check uses `len(rows) >= limit` instead of fetching `limit + 1` rows to confirm truncation precisely.

## Required changes

1. Add `knowledge_graph_id: str | None = None` parameter to `query_graph()` MCP tool.
2. Pass it through `MCPQueryService.execute_cypher_query()` → `IQueryGraphRepository.execute_cypher()`.
3. Apply the `SecureEnclaveFilter` (from task-006) to MCP query results using the caller's user identity.
4. Fix truncation: fetch `max_rows + 1` rows, set `truncated = True` if `len(raw_rows) > max_rows`, return only `max_rows` rows.
5. Write unit tests for each change.

## Notes

- Depends on task-006 which implements the core `SecureEnclaveFilter` in the graph application layer.
- The MCP `query_graph` tool should delegate to the same enclave logic, not re-implement it.
