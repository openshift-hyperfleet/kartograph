# MCP Server

## Purpose
The MCP (Model Context Protocol) server is the primary consumer interface for AI agents. It exposes graph querying and documentation fetching as MCP tools, with authentication via API key or Bearer token.

## Requirements

### Requirement: Graph Query Tool
The system SHALL expose a `query_graph` MCP tool for executing read-only Cypher queries.

#### Scenario: Successful query
- GIVEN an authenticated MCP client
- WHEN the client calls `query_graph` with a valid Cypher query
- THEN the query executes against the caller's tenant graph
- AND the results are returned with rows, row count, truncation flag, and execution time

#### Scenario: Optional KnowledgeGraph filter
- GIVEN a `query_graph` call with an optional `knowledge_graph_id` parameter
- WHEN the parameter is provided
- THEN results are filtered to only that KnowledgeGraph
- AND when omitted, results span all KnowledgeGraphs in the tenant

#### Scenario: Secure enclave redaction
- GIVEN query results containing entities the caller is not authorized to view
- WHEN the results are returned
- THEN unauthorized entities are redacted to only their ID
- AND the graph topology (which entities exist and are connected) is preserved

#### Scenario: Write operation rejected
- GIVEN a Cypher query containing CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, or LOAD
- WHEN the query is submitted
- THEN it is rejected with error type "forbidden"

#### Scenario: Query timeout
- GIVEN a query that exceeds the timeout (default 30 seconds, max 60 seconds)
- WHEN the query is executed
- THEN it is terminated and returned with error type "timeout"

#### Scenario: Result limiting
- GIVEN a query without a LIMIT clause
- WHEN the query is executed
- THEN a LIMIT is automatically applied (default 1000, max 10000)

#### Scenario: Result truncation flag
- GIVEN a query whose result set may exceed the limit
- WHEN the results are returned
- THEN the server SHOULD fetch `limit + 1` rows and set `truncated` to true only if more than `limit` rows were available
- AND the response returns at most `limit` rows

#### Scenario: Internal property filtering
- GIVEN query results containing internal properties (e.g., `all_content_lower`)
- WHEN the results are returned to the client
- THEN internal properties are stripped from the response

### Requirement: Documentation Fetch Tool
The system SHALL expose a `fetch_documentation_source` MCP tool for retrieving file content from GitHub and GitLab.

#### Scenario: Fetch from GitHub
- GIVEN a GitHub blob URL (e.g., `https://github.com/owner/repo/blob/main/file.adoc`)
- WHEN the tool is called
- THEN the file content is fetched via the GitHub API
- AND AsciiDoc metadata and comments are stripped

#### Scenario: Fetch from GitLab
- GIVEN a GitLab blob URL (e.g., `https://gitlab.com/owner/repo/-/blob/main/file.adoc`)
- WHEN the tool is called
- THEN the file content is fetched via the GitLab API

#### Scenario: Private repository with token
- GIVEN a private repository URL and an access token (via `x-github-pat` or `x-gitlab-pat` header)
- WHEN the tool is called
- THEN the token is used for authentication against the provider API

#### Scenario: Self-hosted instance
- GIVEN a URL pointing to a GitHub Enterprise or self-hosted GitLab instance
- WHEN the tool is called
- THEN the correct API endpoint is derived from the hostname

#### Scenario: Invalid URL format
- GIVEN a URL that does not match GitHub or GitLab blob patterns
- WHEN the tool is called
- THEN an error response is returned

### Requirement: Agent Instructions Resource
The system SHALL expose agent instructions as an MCP resource.

#### Scenario: Read instructions
- GIVEN the agent instructions file exists at startup
- WHEN an MCP client reads the `instructions://agent` resource
- THEN the cached instructions content is returned

#### Scenario: Missing instructions at startup
- GIVEN the agent instructions file does not exist
- WHEN the application starts
- THEN startup fails immediately (fail-fast)

### Requirement: MCP Authentication
The system SHALL authenticate MCP requests via API key or Bearer token.

#### Scenario: API key authentication
- GIVEN a valid `X-API-Key` header
- WHEN the MCP request is processed
- THEN the request is authenticated using the API key's creator identity
- AND the tenant is resolved from the API key's tenant scope

#### Scenario: Bearer token authentication
- GIVEN a valid `Authorization: Bearer` header (and no API key)
- WHEN the MCP request is processed
- THEN the JWT is validated
- AND the tenant is resolved from the `X-Tenant-ID` header

#### Scenario: No credentials
- GIVEN a request with no authentication headers
- WHEN the MCP request is processed
- THEN a 401 response is returned

#### Scenario: Authentication service unavailable
- GIVEN a request when the authentication backend is unreachable
- WHEN the MCP request is processed
- THEN a 503 response is returned

### Requirement: Apache AGE Single-Column Return
The system SHALL handle Apache AGE's single-column return constraint.

#### Scenario: Node return
- GIVEN a query returning a single node
- WHEN the result is formatted
- THEN it is wrapped as `{"node": {...properties...}}`

#### Scenario: Edge return
- GIVEN a query returning a single edge
- WHEN the result is formatted
- THEN it is wrapped as `{"edge": {...properties...}}`

#### Scenario: Map return (multiple values)
- GIVEN a query returning a map (e.g., `RETURN {name: n.name, label: label(n)}`)
- WHEN the result is formatted
- THEN map keys are preserved with nested nodes/edges converted to dictionaries

#### Scenario: Scalar return
- GIVEN a query returning a scalar value (e.g., count)
- WHEN the result is formatted
- THEN it is wrapped as `{"value": scalar}`
