# Testing

NFR: This spec describes the testing philosophy and constraints for Kartograph.

## Purpose
Kartograph follows a "fakes over mocks" testing philosophy. Tests should exercise real code paths wherever practical, replacing dependencies only at infrastructure boundaries with purpose-built fake implementations — not mocking libraries. This produces tests that are closer to production behavior, easier to maintain, and serve as documentation for how interfaces work.

## Requirements

### Requirement: No Mocking Libraries for Domain or Application Logic
The system's tests SHALL NOT use mocking libraries (e.g., `unittest.mock.MagicMock`, `AsyncMock`, `patch`) to replace domain or application-layer collaborators.

#### Scenario: Domain service test
- GIVEN a domain service that depends on a repository port
- WHEN writing a unit test for the service
- THEN the test uses a fake (in-memory) implementation of the repository
- AND does NOT use `MagicMock(spec=...)` or `create_autospec()`

#### Scenario: Aggregate test
- GIVEN a domain aggregate with business logic
- WHEN writing a unit test for the aggregate
- THEN the test exercises the aggregate directly with real value objects
- AND no test doubles are needed (aggregates should be pure logic)

### Requirement: Fakes for Infrastructure Boundaries
The system SHALL provide fake implementations for infrastructure dependencies that are too heavy for unit tests (databases, external services, authorization providers).

#### Scenario: Repository fake
- GIVEN a repository port (e.g., `ITenantRepository`)
- THEN an in-memory fake implementation exists (e.g., `InMemoryTenantRepository`)
- AND the fake is a real class implementing the port interface
- AND the fake captures domain semantics (e.g., uniqueness constraints, not-found behavior)

#### Scenario: Authorization provider fake
- GIVEN code that depends on the authorization provider
- THEN an in-memory fake exists that maintains relationship state
- AND permission checks against the fake compute correct results from stored relationships

#### Scenario: Observability probe fake
- GIVEN code that depends on an observability probe protocol
- THEN a no-op or recording implementation exists as a concrete class
- AND it is NOT replaced with `MagicMock(spec=ProbeProtocol)`

### Requirement: Contract Tests
The system SHOULD verify fake implementations against the same behavioral contract as their production counterparts.

#### Scenario: Shared contract test
- GIVEN a repository port with both a PostgreSQL implementation and an in-memory fake
- WHEN the contract test suite runs
- THEN the same behavioral assertions pass against both implementations
- AND this ensures the fake does not drift from the real implementation

### Requirement: Integration Tests Use Real Infrastructure
The system SHALL use real infrastructure (PostgreSQL, SpiceDB, Keycloak) in integration tests.

#### Scenario: Database integration test
- GIVEN a test marked as integration
- WHEN the test exercises repository behavior
- THEN it runs against a real PostgreSQL database with Apache AGE
- AND no database behavior is faked or mocked

#### Scenario: Authorization integration test
- GIVEN a test that verifies permission enforcement
- WHEN the test runs
- THEN it checks permissions against a real SpiceDB instance
- AND relationships are written and read via the real gRPC client

### Requirement: Mocking is Acceptable Only for Boundaries You Don't Own
The system MAY use mocking libraries for external dependencies with no practical fake (e.g., HTTP clients to third-party APIs, OIDC token endpoints).

#### Scenario: External HTTP call
- GIVEN code that makes an HTTP request to a third-party API (e.g., GitHub, GitLab)
- WHEN writing a unit test
- THEN mocking the HTTP client is acceptable
- AND the mock should be as thin as possible (mock the transport, not the logic)

#### Scenario: Acceptable mock target
- GIVEN a test that needs to replace a dependency
- THEN mocking is acceptable ONLY for: HTTP clients, gRPC channels, filesystem I/O, or clock/time
- AND mocking is NOT acceptable for: domain services, repositories, event handlers, or probe protocols

### Requirement: Fake Implementations as Domain Documentation
Fake implementations SHOULD use domain-meaningful setup methods rather than stub configuration.

#### Scenario: Domain-meaningful setup
- GIVEN an in-memory fake for a credit service
- WHEN a test needs to set up an account on credit hold
- THEN the fake exposes a method like `assume_hold_on(account_id)`
- AND does NOT require the test to configure individual method return values

#### Scenario: Reusable across tests
- GIVEN a fake implementation with domain-meaningful methods
- WHEN multiple test classes need the same setup
- THEN they reuse the fake class and its methods
- AND do NOT each re-stub the same interface with a mocking library

### Requirement: Test Layering
The system SHALL organize tests in layers that match the DDD architecture, with appropriate scope at each layer.

#### Scenario: Domain layer tests (small)
- GIVEN tests for aggregates, value objects, and domain services
- THEN they are fast, require no framework, and use only fakes for ports
- AND they thoroughly cover all business logic branches

#### Scenario: Application layer tests (medium)
- GIVEN tests for application services
- THEN they compose real domain objects with fake infrastructure
- AND they test service orchestration, authorization decisions, and event emission

#### Scenario: Integration tests (large)
- GIVEN tests for the full application stack
- THEN they use real infrastructure via Docker Compose
- AND they focus on transport concerns (HTTP, JSON serialization, status codes), wiring correctness, and end-to-end authorization flows
- AND they accept overlap with lower-layer tests as intentional redundancy
