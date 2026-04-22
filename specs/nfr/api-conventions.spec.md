# API Conventions

NFR: This spec describes REST API conventions that all bounded context presentation layers MUST follow for consistency.

## Purpose
Kartograph exposes REST APIs via FastAPI. This spec defines the conventions for URL structure, HTTP status codes, error response format, and request/response modeling so that all bounded contexts present a uniform interface.

## Requirements

### Requirement: URL Structure
The system SHALL follow consistent URL patterns across all bounded contexts.

#### Scenario: Resource CRUD endpoints
- GIVEN a resource type (e.g., knowledge-graphs)
- THEN the following URL pattern applies:
  - `POST /{context}/{resources}` — create
  - `GET /{context}/{resources}` — list
  - `GET /{context}/{resources}/{id}` — get by ID
  - `PATCH /{context}/{resources}/{id}` — update
  - `DELETE /{context}/{resources}/{id}` — delete

#### Scenario: Scoped creation (parent-child)
- GIVEN a resource that belongs to a parent (e.g., data sources belong to a knowledge graph)
- THEN creation and listing are nested under the parent: `POST /{context}/{parents}/{parent_id}/{children}`
- AND retrieval, update, and delete use the flat path: `GET /{context}/{children}/{id}`

#### Scenario: Sub-resource collections (members)
- GIVEN a resource with a member collection (e.g., workspace members)
- THEN member endpoints are nested: `POST /{context}/{resources}/{id}/members`
- AND individual member operations use: `DELETE /{context}/{resources}/{id}/members/{member_id}`

#### Scenario: Action endpoints
- GIVEN a non-CRUD action on a resource (e.g., trigger sync)
- THEN the action is a POST to a named sub-resource: `POST /{context}/{resources}/{id}/{action}`

#### Scenario: Resource naming
- GIVEN any resource type
- THEN URL segments use plural nouns in kebab-case (e.g., `knowledge-graphs`, `api-keys`, `data-sources`)

#### Scenario: Context prefix
- GIVEN a bounded context with a presentation layer
- THEN all routes are mounted under a context prefix (e.g., `/iam`, `/graph`, `/management`)

### Requirement: HTTP Status Codes
The system SHALL use consistent HTTP status codes across all endpoints.

#### Scenario: Successful operations
- GIVEN a successful operation
- THEN the following status codes apply:
  - `201 Created` — resource creation (returns the created resource)
  - `200 OK` — retrieval, listing, and update (returns the resource or collection)
  - `204 No Content` — deletion (returns no body)

#### Scenario: Client errors
- GIVEN an invalid or unauthorized request
- THEN the following status codes apply:
  - `400 Bad Request` — malformed input (invalid ID format, missing fields)
  - `403 Forbidden` — authenticated but lacks required permission
  - `404 Not Found` — resource does not exist or caller lacks view access (no distinction)
  - `409 Conflict` — business rule violation (duplicate name, last admin, already revoked)
  - `422 Unprocessable Entity` — request is well-formed but semantically invalid

#### Scenario: Server errors
- GIVEN an unexpected failure
- THEN `500 Internal Server Error` is returned with a generic message
- AND internal details are not leaked to the caller

### Requirement: Error Response Format
The system SHALL return errors in a consistent JSON format.

#### Scenario: Single error
- GIVEN any error response (4xx or 5xx)
- THEN the response body follows: `{"detail": "Human-readable error message"}`

#### Scenario: Multiple errors (batch operations)
- GIVEN an operation that can produce multiple errors (e.g., mutation batch)
- THEN the response body follows: `{"detail": {"errors": ["error 1", "error 2"]}}`

#### Scenario: Not-found vs forbidden indistinguishable
- GIVEN a resource the caller cannot view or that does not exist
- THEN the same `404` response is returned in both cases
- AND the error message does not reveal whether the resource exists

### Requirement: Request/Response Models
The system SHALL use Pydantic models for all request and response serialization.

#### Scenario: Field naming
- GIVEN any request or response model
- THEN field names use `snake_case`

#### Scenario: ID format
- GIVEN any resource identifier
- THEN the ID is a 26-character ULID string
- AND invalid IDs are rejected with a `400 Bad Request`

#### Scenario: String validation
- GIVEN a user-provided string field (name, description)
- THEN minimum and maximum lengths are enforced via Pydantic field constraints

#### Scenario: Creation response
- GIVEN a successful resource creation
- THEN the full resource representation is returned in the response body

#### Scenario: Timestamps
- GIVEN a response model with timestamps
- THEN `created_at` and `updated_at` are serialized as ISO 8601 strings

### Requirement: Authentication Dependencies
The system SHALL enforce authentication via FastAPI dependency injection.

#### Scenario: Tenant-scoped operations
- GIVEN an endpoint that operates within a tenant
- THEN the `get_current_user` dependency is required (resolves JWT + tenant context)

#### Scenario: Bootstrap operations
- GIVEN an endpoint that operates across tenants (e.g., list tenants, create tenant)
- THEN the `get_authenticated_user` dependency is required (resolves JWT only, no tenant context)
