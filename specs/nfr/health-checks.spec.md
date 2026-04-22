# Health Checks

NFR: This spec describes operational health check endpoints used by container orchestration and monitoring.

## Purpose
Kartograph exposes health check endpoints for liveness and readiness probing. These endpoints are used by Kubernetes to determine whether the application is running and able to serve traffic.

## Requirements

### Requirement: Basic Health Check
The system SHALL expose a basic health check endpoint.

#### Scenario: Application is running
- GIVEN the application has started
- WHEN `GET /health` is called
- THEN a 200 response is returned with `{"status": "ok"}`

### Requirement: Database Health Check
The system SHALL expose a database connectivity health check endpoint.

#### Scenario: Database is reachable
- GIVEN the application is running and the database is available
- WHEN `GET /health/db` is called
- THEN a 200 response is returned confirming database connectivity

#### Scenario: Database is unreachable
- GIVEN the application is running but the database is unavailable
- WHEN `GET /health/db` is called
- THEN a 503 Service Unavailable response is returned
- AND the response body contains an error message indicating database connectivity failure

### Requirement: Startup Ordering
The system SHALL wait for dependent services to be ready before accepting traffic.

#### Scenario: Database migration dependency
- GIVEN the application is starting
- WHEN database migrations have not yet completed
- THEN the application waits for migration completion before starting

#### Scenario: Authorization schema dependency
- GIVEN the application is starting
- WHEN the SpiceDB schema has not yet been loaded
- THEN the application waits for schema initialization before starting
