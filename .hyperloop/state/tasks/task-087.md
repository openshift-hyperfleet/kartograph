---
id: task-087
title: Add knowledge_graphs://accessible MCP resource
spec_ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
status: not_started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: 'feat(query): add knowledge_graphs://accessible MCP resource'
pr_description: "## What and Why\n\nThe MCP server spec (Requirement: Knowledge Graphs\
  \ Resource) mandates that the\nsystem exposes a `knowledge_graphs://accessible`\
  \ MCP resource that lists all\nKnowledgeGraphs the authenticated MCP caller has\
  \ `view` permission on within\ntheir tenant. This resource is currently absent from\n\
  `src/api/query/presentation/mcp.py` — only the `instructions://agent` resource\n\
  is registered.\n\nAI agents using the MCP server need a way to discover which knowledge\
  \ graphs\nexist before formulating queries. Without this resource they have no structured\n\
  entry-point to the platform's data scope.\n\n## Spec Requirements Satisfied\n\n\
  - **Scenario: List accessible knowledge graphs** — `knowledge_graphs://accessible`\n\
  \  returns every KG for which the caller holds `view` permission; each entry\n \
  \ includes `id`, `name`, and `description`. KGs the caller cannot access are\n \
  \ omitted entirely.\n- **Scenario: No accessible knowledge graphs** — resource returns\
  \ an empty list\n  when SpiceDB yields no results.\n\n## Key Design Decisions\n\n\
  - Uses `authz.lookup_resources(resource_type=\"knowledge_graph\", permission=\"\
  view\",\n  subject=format_subject(...))` to enumerate permitted KGs from SpiceDB.\n\
  - Fetches KG metadata (name, description) from the Management context's\n  `KnowledgeGraphRepository`\
  \ by the returned IDs. This cross-context wiring\n  belongs in `infrastructure/mcp_dependencies.py`\
  \ alongside the existing\n  `get_schema_service_for_mcp()` pattern.\n- The resource\
  \ function is synchronous with `async def` — same pattern as other\n  FastMCP async\
  \ tools already in the codebase.\n- Per-call SpiceDB lookup (no caching at resource\
  \ level); individual KG metadata\n  fetches are batched or iterated depending on\
  \ result set size.\n- The resource is registered with `@mcp.resource(uri=\"knowledge_graphs://accessible\"\
  ,\n  ...)` following the existing `instructions://agent` pattern.\n\n## Files /\
  \ Areas Affected\n\n- `src/api/query/presentation/mcp.py` — add new `@mcp.resource`\
  \ handler\n- `src/api/infrastructure/mcp_dependencies.py` — add\n  `get_management_kg_repository_for_mcp()`\
  \ or equivalent composition helper\n- `src/api/tests/unit/query/test_mcp_tools.py`\
  \ (or new\n  `test_mcp_knowledge_graphs_resource.py`) — unit tests for both scenarios\n\
  - `src/api/tests/integration/test_query_mcp.py` — integration coverage\n\n## How\
  \ to Verify\n\n1. Run `make test-unit` — new unit tests must pass.\n2. Start a dev\
  \ instance (`make instance-up`) and use an MCP client to read\n   `knowledge_graphs://accessible`.\
  \ Expect a JSON list of KGs scoped to the\n   authenticated tenant with only those\
  \ the API key's user can view.\n3. Create a KG the user does NOT have view permission\
  \ on; confirm it is absent\n   from the resource response.\n4. Revoke all KG permissions;\
  \ confirm the resource returns `[]`.\n\n## Caveats / Follow-up\n\n- The `lookup_resources`\
  \ call is tenant-unscoped at the SpiceDB level; the tenant\n  scope is enforced\
  \ by the relationship model (every KG belongs to a workspace\n  which belongs to\
  \ a tenant). The resource should only return KGs reachable via\n  the caller's tenant\
  \ relationships — verify this doesn't leak cross-tenant data.\n- If SpiceDB returns\
  \ a large number of KG IDs, the Management DB query may need\n  batching (`WHERE\
  \ id = ANY(...)` in Postgres)."
---
