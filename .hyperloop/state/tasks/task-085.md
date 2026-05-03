---
id: task-085
title: Add knowledge_graphs://accessible MCP resource
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(query): expose knowledge_graphs://accessible MCP resource"
pr_description: |
  ## What & Why

  The `mcp-server.spec.md` spec was updated to add a new **Requirement:
  Knowledge Graphs Resource**. The spec requires:

  > The system SHALL expose the caller's accessible knowledge graphs as an MCP
  > resource.

  with two scenarios:

  **Scenario: List accessible knowledge graphs**
  > GIVEN an authenticated MCP client
  > WHEN the client reads the `knowledge_graphs://accessible` resource
  > THEN the response contains all knowledge graphs the caller has `view`
  >   permission on within their tenant
  > AND each entry includes the knowledge graph `id`, `name`, and `description`
  > AND knowledge graphs the caller cannot access are omitted entirely

  **Scenario: No accessible knowledge graphs**
  > GIVEN an authenticated MCP client with no accessible knowledge graphs
  > WHEN the client reads the `knowledge_graphs://accessible` resource
  > THEN an empty list is returned

  Currently the MCP server exposes two resources (`instructions://agent` and
  nothing else related to knowledge graphs). AI agents using the MCP interface
  have no way to discover which knowledge graphs they can access without
  executing raw Cypher, which requires knowledge of the graph schema up front.
  This resource gives agents a structured, permission-filtered entry point.

  ## What This PR Does

  ### 1. Cross-context factory in `mcp_dependencies.py`

  Add `get_kg_service_for_mcp()` to
  `src/api/infrastructure/mcp_dependencies.py`:

  ```python
  async def get_kg_service_for_mcp() -> KnowledgeGraphService:
      """Compose KnowledgeGraphService scoped to the current MCP caller's tenant."""
      from management.application.services.knowledge_graph_service import (
          KnowledgeGraphService,
      )
      from management.infrastructure.repositories import (
          KnowledgeGraphRepository, DataSourceRepository, FernetSecretStore,
      )
      from infrastructure.authorization_dependencies import get_spicedb_client
      from infrastructure.database.dependencies import get_async_sessionmaker
      from infrastructure.settings import get_management_settings
      from shared_kernel.middleware.mcp_auth import get_mcp_auth_context

      auth_context = get_mcp_auth_context()
      settings = get_management_settings()
      sessionmaker = get_async_sessionmaker()  # or equivalent helper
      async with sessionmaker() as session:
          kg_repo = KnowledgeGraphRepository(session=session)
          authz = get_spicedb_client()
          return KnowledgeGraphService(
              session=session,
              knowledge_graph_repository=kg_repo,
              authz=authz,
              scope_to_tenant=auth_context.tenant_id,
          )
  ```

  Note: since FastMCP resources are synchronous-compatible but this needs
  async DB access, the resource handler must be `async def` and either use
  FastMCP's async resource support or construct the session inline.
  Inspect how existing async patterns in MCP dependencies work and follow
  the same approach.

  ### 2. New MCP resource in `mcp.py`

  Add to `src/api/query/presentation/mcp.py`:

  ```python
  @mcp.resource(
      uri="knowledge_graphs://accessible",
      name="AccessibleKnowledgeGraphs",
      description="All knowledge graphs the caller has view permission on in their tenant",
      mime_type="application/json",
      annotations={"readOnlyHint": True, "idempotentHint": True},
  )
  async def get_accessible_knowledge_graphs() -> list[dict]:
      """List knowledge graphs accessible to the current MCP caller.

      Returns a JSON list of objects with 'id', 'name', and 'description'.
      Knowledge graphs the caller lacks view permission on are omitted.
      Returns an empty list when the caller has no accessible graphs.
      """
      from infrastructure.mcp_dependencies import get_kg_service_for_mcp
      from shared_kernel.middleware.mcp_auth import get_mcp_auth_context

      auth_context = get_mcp_auth_context()
      service = await get_kg_service_for_mcp()
      kgs = await service.list_all(user_id=auth_context.user_id)

      return [
          {
              "id": kg.id.value,
              "name": kg.name,
              "description": kg.description,
          }
          for kg in kgs
      ]
  ```

  The `KnowledgeGraphService.list_all(user_id, permission=Permission.VIEW)` 
  already implements the permission-filtering logic against SpiceDB — no new
  business logic is needed.

  ## Files Affected

  - `src/api/infrastructure/mcp_dependencies.py` — add
    `get_kg_service_for_mcp()` cross-context factory
  - `src/api/query/presentation/mcp.py` — add
    `@mcp.resource(uri="knowledge_graphs://accessible")`
  - `src/api/tests/unit/query/test_mcp_tools.py` (or a new
    `test_mcp_resources.py`) — new unit tests covering both scenarios

  ## How to Verify

  1. Unit tests pass: `make test-unit`
  2. An MCP client calling `read_resource("knowledge_graphs://accessible")`
     receives a JSON list filtered to graphs the user can view.
  3. A user with no accessible KGs receives `[]`.
  4. Knowledge graphs from other tenants never appear (tenant scoping via
     `scope_to_tenant=auth_context.tenant_id` on `KnowledgeGraphService`).

  ## Design Decisions

  - **Response shape** — `{id, name, description}` exactly as specified.
    Internal fields (`workspace_id`, `created_at`, etc.) are omitted.
  - **Permission level** — `Permission.VIEW` (the spec says "view permission").
    The `list_all()` default is already VIEW; pass it explicitly for clarity.
  - **Cross-context composition** — the factory lives in
    `infrastructure/mcp_dependencies.py`, the established location for MCP
    cross-context wiring (`get_schema_service_for_mcp()` follows the same
    pattern).
  - **No caching** — the resource is per-request because permissions change
    dynamically. `lru_cache` would be incorrect here.

  ## Follow-up

  If task-084 (per-tenant query routing) has introduced a shared async session
  helper for the MCP layer, reuse it here rather than duplicating the
  sessionmaker lookup.
---
