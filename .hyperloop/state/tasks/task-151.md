---
id: task-151
title: "Add integration tests for MCP Knowledge Graphs Resource"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add integration tests for MCP knowledge-graphs://accessible resource"
pr_description: |
  ## What and Why

  The MCP Server spec's "Knowledge Graphs Resource" requirement (added in commit
  `6bea4557d`) defines two scenarios:

  > **Requirement: Knowledge Graphs Resource**
  >
  > **Scenario: List accessible knowledge graphs**
  > "GIVEN an authenticated MCP client
  >  WHEN the client reads the `knowledge_graphs://accessible` resource
  >  THEN the response contains all knowledge graphs the caller has `view`
  >  permission on within their tenant
  >  AND each entry includes the knowledge graph `id`, `name`, and `description`
  >  AND knowledge graphs the caller cannot access are omitted entirely"
  >
  > **Scenario: No accessible knowledge graphs**
  > "GIVEN an authenticated MCP client with no accessible knowledge graphs
  >  WHEN the client reads the `knowledge_graphs://accessible` resource
  >  THEN an empty list is returned"

  Both scenarios are implemented in `get_accessible_knowledge_graphs()` in
  `src/api/query/presentation/mcp.py` and verified by comprehensive unit tests
  in `src/api/tests/unit/query/test_mcp_knowledge_graphs_resource.py`.

  However, no integration test exercises these scenarios against a real
  PostgreSQL + SpiceDB instance through the actual HTTP MCP endpoint. This was
  identified as a gap analogous to the per-tenant graph routing gap addressed
  by task-150: both requirements were added in the same commit (`6bea4557d`)
  but only the routing requirement received an integration test task.

  The Knowledge Graphs Resource specifically involves SpiceDB `lookup_resources`
  calls to find which KGs the caller has VIEW permission on, followed by a
  database lookup for names and descriptions. This cross-context, cross-system
  data flow deserves end-to-end verification against real infrastructure —
  unit fakes cannot prove the SpiceDB resource lookup and management DB join
  work correctly together.

  ## Spec Requirements Satisfied

  `specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`

  - **Requirement: Knowledge Graphs Resource — Scenario: List accessible knowledge graphs**
    Verify the resource returns id/name/description for each KG the caller has
    VIEW permission on in SpiceDB, and omits KGs the caller cannot access.

  - **Requirement: Knowledge Graphs Resource — Scenario: No accessible knowledge graphs**
    Verify the resource returns an empty list when SpiceDB returns no accessible
    KG IDs for the caller.

  ## Key Design Decisions

  **Integration tests run against `make instance-up`** (PostgreSQL + SpiceDB,
  fake OIDC provider). Mark tests with `@pytest.mark.integration`.

  **Test via the HTTP MCP endpoint** (not just the service layer directly),
  to exercise the full stack: API key auth → MCP auth middleware →
  `get_accessible_knowledge_graphs()` resource → `MCPKnowledgeGraphsService` →
  SpiceDB `lookup_resources` → management DB `find_by_ids_and_tenant`.

  **Test structure** — two test classes:

  1. **`TestKnowledgeGraphsResourceListsAccessible`**: Create a tenant, provision
     two knowledge graphs, grant VIEW permission on one via SpiceDB, create an
     API key scoped to that tenant, then call the `knowledge-graphs://accessible`
     resource and assert:
     - Only the KG with VIEW permission is returned
     - The response includes `id`, `name`, and `description`
     - The inaccessible KG is absent from the response

  2. **`TestKnowledgeGraphsResourceEmpty`**: Create a tenant, provision a
     knowledge graph but grant NO VIEW permissions in SpiceDB, then call the
     resource and assert an empty list is returned.

  Follow the pattern established by `test_secure_enclave_mcp.py` for setting
  up test tenants, creating knowledge graphs via the management API, and calling
  MCP tools/resources via HTTP with API key authentication.

  ## What Files Are Affected

  - **New file**:
    `src/api/tests/integration/test_query_mcp_kg_resource.py`
    — Two test classes covering the two Knowledge Graphs Resource scenarios.
    Marks: `@pytest.mark.integration`.

  - No implementation files change — the behavior is already correct;
    only integration-level test coverage is missing.

  ## How to Verify

  ```bash
  # Start isolated dev instance
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance

  # Run the new integration tests
  cd src/api && uv run pytest tests/integration/test_query_mcp_kg_resource.py \
      -v -m integration

  # Full integration suite — confirm no regressions
  make test-integration
  ```

  ## Caveats

  - SpiceDB relationships written during tests must be cleaned up in fixture
    teardown to avoid contaminating other integration tests.
  - Use the management API to create knowledge graphs (not raw DB inserts) to
    ensure SpiceDB relationships are properly written for the KG entity.
  - The resource URI is `knowledge-graphs://accessible` (hyphen, not underscore)
    per the implementation note in `mcp.py` (RFC 3986 disallows underscores in
    URI schemes).
  - API key creation via `POST /iam/api-keys` requires a tenant context; ensure
    the integration test creates the API key scoped to the test tenant.
  - The `knowledge_graphs://accessible` resource is only accessible via the MCP
    endpoint (not a REST endpoint), so tests must use the MCP HTTP transport
    as demonstrated in `test_query_mcp_http.py`.
---
