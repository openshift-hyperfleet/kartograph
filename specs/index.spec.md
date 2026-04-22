# Kartograph Specifications

## Purpose
Behavioral contracts for the Kartograph knowledge graph platform. Each spec describes what the system does — not how it's built.

Kartograph is organized around **bounded contexts** following Domain-Driven Design. Each context owns its own aggregates, services, and API surface.

---

## Bounded Contexts

### [IAM](iam/) — Identity & Access Management
Who can do what. Multi-tenant isolation, role-based access, API key authentication.

| Spec | Scope |
|------|-------|
| [Tenants](iam/tenants.spec.md) | Tenant lifecycle, member management, last-admin protection |
| [Workspaces](iam/workspaces.spec.md) | Workspace hierarchy, member roles, root workspace behavior |
| [Groups](iam/groups.spec.md) | Group membership and workspace access inheritance |
| [API Keys](iam/api-keys.spec.md) | API key issuance, authentication, scoping |
| [Users](iam/users.spec.md) | User identity resolution and profile |
| [Authorization](iam/authorization.spec.md) | SpiceDB permission model across all IAM resources |

### [Graph](graph/) — Knowledge Graph Engine
The persistence and query engine for property graph data.

| Spec | Scope |
|------|-------|
| [Mutations](graph/mutations.spec.md) | Applying mutation logs to the graph |
| [Queries](graph/queries.spec.md) | Reading nodes, edges, and subgraphs |
| [Schema](graph/schema.spec.md) | Type definitions and schema management |
| [Bulk Loading](graph/bulk-loading.spec.md) | High-throughput graph ingestion |

### [Management](management/) — Control Plane
CRUD for platform resources: knowledge graphs, data sources, credentials.

| Spec | Scope |
|------|-------|
| [Knowledge Graphs](management/knowledge-graphs.spec.md) | Knowledge graph configuration lifecycle |
| [Data Sources](management/data-sources.spec.md) | Data source configuration and sync runs |
| [Credentials](management/credentials.spec.md) | Encrypted credential storage |

### [Query](query/) — Consumer Interface
Read access for end-users and AI agents via MCP.

| Spec | Scope |
|------|-------|
| [MCP Server](query/mcp-server.spec.md) | Model Context Protocol tools and authentication |
| [Query Execution](query/query-execution.spec.md) | Translating questions into graph queries |

### [Shared Kernel](shared-kernel/) — Cross-Cutting Contracts
Capabilities shared across bounded contexts.

| Spec | Scope |
|------|-------|
| [JWT Authentication](shared-kernel/jwt-authentication.spec.md) | OIDC token validation and user identity extraction |
| [SpiceDB Authorization](shared-kernel/spicedb-authorization.spec.md) | Permission checks, relationship writes, resource lookups |
| [Outbox](shared-kernel/outbox.spec.md) | Transactional event publishing pattern |
| [Tenant Context](shared-kernel/tenant-context.spec.md) | Request-scoped tenant resolution middleware |

---

## Non-Functional Requirements

| Spec | Scope |
|------|-------|
| [Observability](nfr/observability.spec.md) | Domain-oriented observability probe contracts |
| [Architecture](nfr/architecture.spec.md) | DDD layering rules, bounded context isolation |
| [Testing](nfr/testing.spec.md) | Fakes over mocks, contract tests, test layering |
