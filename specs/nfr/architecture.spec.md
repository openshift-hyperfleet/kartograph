# Architecture

NFR: This spec describes structural constraints enforced via automated tests, not domain behavior.

## Purpose
Kartograph enforces DDD layering rules and bounded context isolation at import-time using pytest-archon. These rules prevent accidental coupling and maintain a clean dependency graph that could support future decomposition into microservices.

## Requirements

### Requirement: Domain Layer Isolation
The domain layer of each bounded context SHALL NOT depend on infrastructure, application, or framework code.

#### Scenario: Domain independence
- GIVEN the domain layer of any bounded context (e.g., `graph.domain`, `iam.domain`)
- THEN it does not import from its own infrastructure or application layers
- AND it does not import FastAPI, Starlette, or other web framework modules

### Requirement: Ports Layer Isolation
The ports layer SHALL NOT depend on infrastructure or application code.

#### Scenario: Ports as contracts
- GIVEN the ports layer of any bounded context
- THEN it does not import from infrastructure (implementations are injected, not imported)
- AND it does not import from the application layer

### Requirement: Application Layer Restrictions
The application layer SHALL depend only on domain and ports, not infrastructure.

#### Scenario: Application dependencies
- GIVEN the application layer of any bounded context
- THEN it may import from domain and ports within its own context
- AND it does not import from infrastructure

### Requirement: Infrastructure Layer Restrictions
The infrastructure layer SHALL NOT depend on the application layer.

#### Scenario: Infrastructure independence
- GIVEN the infrastructure layer of any bounded context
- THEN it may import from domain and ports (to implement port contracts)
- AND it does not import from the application layer (it is used by application, not the reverse)

### Requirement: Bounded Context Isolation
Each bounded context SHALL NOT import from another context's domain, ports, or application layers.

#### Scenario: Cross-context isolation
- GIVEN the Query bounded context
- THEN it does not import from IAM, Management, Ingestion, or Extraction domain/application layers
- AND cross-context integration happens only through shared kernel or composition infrastructure

### Requirement: Shared Kernel Independence
The shared kernel SHALL NOT depend on any bounded context.

#### Scenario: Shared kernel as foundation
- GIVEN the shared kernel
- THEN it does not import from graph, query, iam, management, ingestion, or extraction contexts
- AND it does not import from the infrastructure layer
- AND bounded contexts may depend on it (one-way dependency)

### Requirement: Composition Layer Exception
The system SHALL allow a single composition layer to wire bounded contexts together.

#### Scenario: MCP composition
- GIVEN the MCP dependency composition module (`infrastructure.mcp_dependencies`)
- THEN it is permitted to import from multiple bounded contexts
- AND this is the only module with cross-context import permissions

### Requirement: Outbox Infrastructure Isolation
The generic outbox infrastructure SHALL NOT depend on any bounded context's internals.

#### Scenario: Outbox independence
- GIVEN the generic outbox infrastructure (`infrastructure.outbox`)
- THEN it does not import from any bounded context's domain, ports, or application layers
- AND context-specific event translation lives within each context's own infrastructure layer
