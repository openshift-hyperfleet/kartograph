# Application Lifecycle

NFR: This spec describes the application startup and shutdown sequence.

## Purpose
Kartograph manages a complex startup sequence — initializing database connections, bootstrapping default resources in single-tenant mode, starting the outbox worker, and mounting the MCP server. Shutdown reverses this sequence gracefully.

## Requirements

### Requirement: Single-Tenant Mode Bootstrap
The system SHALL provision a default tenant and workspace on startup when running in single-tenant mode.

#### Scenario: Default tenant and workspace
- GIVEN single-tenant mode is enabled (the default)
- AND a write database session is available
- WHEN the application starts
- THEN a default tenant is created (or verified to exist) using the configured tenant name
- AND a root workspace is created within the default tenant
- AND the workspace name defaults to the tenant name if not explicitly configured

#### Scenario: Multi-tenant mode
- GIVEN single-tenant mode is disabled
- WHEN the application starts
- THEN no default tenant or workspace is created

### Requirement: Outbox Worker Lifecycle
The system SHALL start and stop the outbox worker as part of the application lifecycle.

#### Scenario: Outbox enabled
- GIVEN outbox processing is enabled
- WHEN the application starts
- THEN the outbox worker begins processing events from all bounded contexts (IAM, Management)
- AND the worker listens for PostgreSQL NOTIFY events for real-time processing

#### Scenario: Graceful shutdown
- GIVEN the outbox worker is running
- WHEN the application shuts down
- THEN the worker stops accepting new events
- AND in-progress event processing completes before shutdown

### Requirement: Database Connection Lifecycle
The system SHALL initialize and dispose database connections as part of the application lifecycle.

#### Scenario: Startup
- GIVEN the application is starting
- WHEN the lifespan begins
- THEN database engines are initialized
- AND connection pools are created

#### Scenario: Shutdown
- GIVEN the application is shutting down
- WHEN the lifespan ends
- THEN database engines are disposed
- AND connection pools are released

### Requirement: Default Configuration
The system SHALL use sensible defaults for single-tenant deployments.

#### Scenario: Default settings
- GIVEN no explicit configuration overrides
- THEN single-tenant mode is enabled
- AND the default tenant name is "default"
- AND the default workspace name falls back to the tenant name
- AND bootstrap admin usernames list is empty (no auto-admin provisioning)
