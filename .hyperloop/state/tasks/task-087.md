---
id: task-087
title: Add knowledge_graphs://accessible MCP resource
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(query): add knowledge_graphs://accessible MCP resource"
pr_description: |
  ## What and Why

  The MCP server spec (Requirement: Knowledge Graphs Resource) mandates that the
  system exposes a `knowledge_graphs://accessible` MCP resource that lists all
  KnowledgeGraphs the authenticated MCP caller has `view` permission on within
  their tenant. This resource is currently absent from
  `src/api/query/presentation/mcp.py` — only the `instructions://agent` resource
  is registered.

  AI agents using the MCP server need a way to discover which knowledge graphs
  exist before formulating queries. Without this resource they have no structured
  entry-point to the platform's data scope.

  ## Spec Requirements Satisfied

  - **Scenario: List accessible knowledge graphs** — `knowledge_graphs://accessible`
    returns every KG for which the caller holds `view` permission; each entry
    includes `id`, `name`, and `description`. KGs the caller cannot access are
    omitted entirely.
  - **Scenario: No accessible knowledge graphs** — resource returns an empty list
    when SpiceDB yields no results.

  ## Key Design Decisions

  - Uses `authz.lookup_resources(resource_type="knowledge_graph", permission="view",
    subject=format_subject(...))` to enumerate permitted KGs from SpiceDB.
  - Fetches KG metadata (name, description) from the Management context's
    `KnowledgeGraphRepository` by the returned IDs. This cross-context wiring
    belongs in `infrastructure/mcp_dependencies.py` alongside the existing
    `get_schema_service_for_mcp()` pattern.
  - The resource function is synchronous with `async def` — same pattern as other
    FastMCP async tools already in the codebase.
  - Per-call SpiceDB lookup (no caching at resource level); individual KG metadata
    fetches are batched or iterated depending on result set size.
  - The resource is registered with `@mcp.resource(uri="knowledge_graphs://accessible",
    ...)` following the existing `instructions://agent` pattern.

  ## Files / Areas Affected

  - `src/api/query/presentation/mcp.py` — add new `@mcp.resource` handler
  - `src/api/infrastructure/mcp_dependencies.py` — add
    `get_management_kg_repository_for_mcp()` or equivalent composition helper
  - `src/api/tests/unit/query/test_mcp_tools.py` (or new
    `test_mcp_knowledge_graphs_resource.py`) — unit tests for both scenarios
  - `src/api/tests/integration/test_query_mcp.py` — integration coverage

  ## How to Verify

  1. Run `make test-unit` — new unit tests must pass.
  2. Start a dev instance (`make instance-up`) and use an MCP client to read
     `knowledge_graphs://accessible`. Expect a JSON list of KGs scoped to the
     authenticated tenant with only those the API key's user can view.
  3. Create a KG the user does NOT have view permission on; confirm it is absent
     from the resource response.
  4. Revoke all KG permissions; confirm the resource returns `[]`.

  ## Caveats / Follow-up

  - The `lookup_resources` call is tenant-unscoped at the SpiceDB level; the tenant
    scope is enforced by the relationship model (every KG belongs to a workspace
    which belongs to a tenant). The resource should only return KGs reachable via
    the caller's tenant relationships — verify this doesn't leak cross-tenant data.
  - If SpiceDB returns a large number of KG IDs, the Management DB query may need
    batching (`WHERE id = ANY(...)` in Postgres).
---
