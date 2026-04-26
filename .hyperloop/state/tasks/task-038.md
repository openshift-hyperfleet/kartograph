---
id: task-038
title: MCP tenant context — API key and Bearer token authentication
spec_ref: specs/shared-kernel/tenant-context.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Spec Gap

`specs/shared-kernel/tenant-context.spec.md` — **MCP Authentication** requirement.
No existing task covers the three scenarios under this requirement.

## Requirement

The MCP server (`/query/mcp`) must support two authentication paths for tenant
resolution, distinct from the standard REST API dependency chain:

1. **API key path** — A valid `X-API-Key` header resolves the tenant directly from
   the key's tenant scope. No `X-Tenant-ID` header is needed. This enables headless
   tool calls where the caller's API key implicitly scopes the request.

2. **Bearer token fallback** — When no API key is present, the JWT path applies.
   The tenant is resolved from the `X-Tenant-ID` header (same rules as REST: invalid
   or unauthorized header → 400 / 403).

3. **Error cases** — No valid credentials → 401. Auth backend unreachable → 503.

## Scenarios to implement (from spec)

### Scenario: API key authentication
- GIVEN an MCP request with a valid `X-API-Key` header
- WHEN the request is authenticated
- THEN the tenant is resolved from the API key's tenant scope (no header needed)
- AND the auth context is set for downstream MCP tools

### Scenario: Bearer token fallback
- GIVEN an MCP request with a Bearer token but no API key
- WHEN the request is authenticated
- THEN the JWT is validated
- AND the tenant is resolved from the `X-Tenant-ID` header

### Scenario: Authentication failure
- GIVEN an MCP request with no valid credentials
- WHEN the request is authenticated
- THEN a 401 response is returned

### Scenario: Service unavailability
- GIVEN an MCP request when the authentication backend is unreachable
- WHEN the request is authenticated
- THEN a 503 response is returned

## TDD approach

Write integration tests first, targeting the MCP endpoint and exercising all four
scenarios above. Then implement (or extend) the FastAPI dependency that handles
authentication branching: API key lookup → tenant scope extraction; JWT validation
→ `X-Tenant-ID` resolution; appropriate error responses for missing credentials and
backend failures.
