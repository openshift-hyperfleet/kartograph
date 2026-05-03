---
id: task-085
title: Add knowledge_graphs://accessible MCP resource
spec_ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
status: in_progress
phase: spec-review
deps: []
round: 1
branch: hyperloop/task-085
pr: https://github.com/openshift-hyperfleet/kartograph/pull/550
pr_title: 'feat(query): expose knowledge_graphs://accessible MCP resource'
pr_description: "## What & Why\n\nThe `mcp-server.spec.md` spec was updated to add\
  \ a new **Requirement:\nKnowledge Graphs Resource**. The spec requires:\n\n> The\
  \ system SHALL expose the caller's accessible knowledge graphs as an MCP\n> resource.\n\
  \nwith two scenarios:\n\n**Scenario: List accessible knowledge graphs**\n> GIVEN\
  \ an authenticated MCP client\n> WHEN the client reads the `knowledge_graphs://accessible`\
  \ resource\n> THEN the response contains all knowledge graphs the caller has `view`\n\
  >   permission on within their tenant\n> AND each entry includes the knowledge graph\
  \ `id`, `name`, and `description`\n> AND knowledge graphs the caller cannot access\
  \ are omitted entirely\n\n**Scenario: No accessible knowledge graphs**\n> GIVEN\
  \ an authenticated MCP client with no accessible knowledge graphs\n> WHEN the client\
  \ reads the `knowledge_graphs://accessible` resource\n> THEN an empty list is returned\n\
  \nCurrently the MCP server exposes two resources (`instructions://agent` and\nnothing\
  \ else related to knowledge graphs). AI agents using the MCP interface\nhave no\
  \ way to discover which knowledge graphs they can access without\nexecuting raw\
  \ Cypher, which requires knowledge of the graph schema up front.\nThis resource\
  \ gives agents a structured, permission-filtered entry point.\n\n## What This PR\
  \ Does\n\n### 1. Cross-context factory in `mcp_dependencies.py`\n\nAdd `get_kg_service_for_mcp()`\
  \ to\n`src/api/infrastructure/mcp_dependencies.py`:\n\n```python\nasync def get_kg_service_for_mcp()\
  \ -> KnowledgeGraphService:\n    \"\"\"Compose KnowledgeGraphService scoped to the\
  \ current MCP caller's tenant.\"\"\"\n    from management.application.services.knowledge_graph_service\
  \ import (\n        KnowledgeGraphService,\n    )\n    from management.infrastructure.repositories\
  \ import (\n        KnowledgeGraphRepository, DataSourceRepository, FernetSecretStore,\n\
  \    )\n    from infrastructure.authorization_dependencies import get_spicedb_client\n\
  \    from infrastructure.database.dependencies import get_async_sessionmaker\n \
  \   from infrastructure.settings import get_management_settings\n    from shared_kernel.middleware.mcp_auth\
  \ import get_mcp_auth_context\n\n    auth_context = get_mcp_auth_context()\n   \
  \ settings = get_management_settings()\n    sessionmaker = get_async_sessionmaker()\
  \  # or equivalent helper\n    async with sessionmaker() as session:\n        kg_repo\
  \ = KnowledgeGraphRepository(session=session)\n        authz = get_spicedb_client()\n\
  \        return KnowledgeGraphService(\n            session=session,\n         \
  \   knowledge_graph_repository=kg_repo,\n            authz=authz,\n            scope_to_tenant=auth_context.tenant_id,\n\
  \        )\n```\n\nNote: since FastMCP resources are synchronous-compatible but\
  \ this needs\nasync DB access, the resource handler must be `async def` and either\
  \ use\nFastMCP's async resource support or construct the session inline.\nInspect\
  \ how existing async patterns in MCP dependencies work and follow\nthe same approach.\n\
  \n### 2. New MCP resource in `mcp.py`\n\nAdd to `src/api/query/presentation/mcp.py`:\n\
  \n```python\n@mcp.resource(\n    uri=\"knowledge_graphs://accessible\",\n    name=\"\
  AccessibleKnowledgeGraphs\",\n    description=\"All knowledge graphs the caller\
  \ has view permission on in their tenant\",\n    mime_type=\"application/json\"\
  ,\n    annotations={\"readOnlyHint\": True, \"idempotentHint\": True},\n)\nasync\
  \ def get_accessible_knowledge_graphs() -> list[dict]:\n    \"\"\"List knowledge\
  \ graphs accessible to the current MCP caller.\n\n    Returns a JSON list of objects\
  \ with 'id', 'name', and 'description'.\n    Knowledge graphs the caller lacks view\
  \ permission on are omitted.\n    Returns an empty list when the caller has no accessible\
  \ graphs.\n    \"\"\"\n    from infrastructure.mcp_dependencies import get_kg_service_for_mcp\n\
  \    from shared_kernel.middleware.mcp_auth import get_mcp_auth_context\n\n    auth_context\
  \ = get_mcp_auth_context()\n    service = await get_kg_service_for_mcp()\n    kgs\
  \ = await service.list_all(user_id=auth_context.user_id)\n\n    return [\n     \
  \   {\n            \"id\": kg.id.value,\n            \"name\": kg.name,\n      \
  \      \"description\": kg.description,\n        }\n        for kg in kgs\n    ]\n\
  ```\n\nThe `KnowledgeGraphService.list_all(user_id, permission=Permission.VIEW)`\
  \ \nalready implements the permission-filtering logic against SpiceDB — no new\n\
  business logic is needed.\n\n## Files Affected\n\n- `src/api/infrastructure/mcp_dependencies.py`\
  \ — add\n  `get_kg_service_for_mcp()` cross-context factory\n- `src/api/query/presentation/mcp.py`\
  \ — add\n  `@mcp.resource(uri=\"knowledge_graphs://accessible\")`\n- `src/api/tests/unit/query/test_mcp_tools.py`\
  \ (or a new\n  `test_mcp_resources.py`) — new unit tests covering both scenarios\n\
  \n## How to Verify\n\n1. Unit tests pass: `make test-unit`\n2. An MCP client calling\
  \ `read_resource(\"knowledge_graphs://accessible\")`\n   receives a JSON list filtered\
  \ to graphs the user can view.\n3. A user with no accessible KGs receives `[]`.\n\
  4. Knowledge graphs from other tenants never appear (tenant scoping via\n   `scope_to_tenant=auth_context.tenant_id`\
  \ on `KnowledgeGraphService`).\n\n## Design Decisions\n\n- **Response shape** —\
  \ `{id, name, description}` exactly as specified.\n  Internal fields (`workspace_id`,\
  \ `created_at`, etc.) are omitted.\n- **Permission level** — `Permission.VIEW` (the\
  \ spec says \"view permission\").\n  The `list_all()` default is already VIEW; pass\
  \ it explicitly for clarity.\n- **Cross-context composition** — the factory lives\
  \ in\n  `infrastructure/mcp_dependencies.py`, the established location for MCP\n\
  \  cross-context wiring (`get_schema_service_for_mcp()` follows the same\n  pattern).\n\
  - **No caching** — the resource is per-request because permissions change\n  dynamically.\
  \ `lru_cache` would be incorrect here.\n\n## Follow-up\n\nIf task-084 (per-tenant\
  \ query routing) has introduced a shared async session\nhelper for the MCP layer,\
  \ reuse it here rather than duplicating the\nsessionmaker lookup."
---
