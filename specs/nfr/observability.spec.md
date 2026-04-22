# Observability

NFR: This spec describes a non-functional architectural pattern, not domain behavior.

## Purpose
Kartograph uses Domain-Oriented Observability: instrumentation is expressed through domain-specific probe interfaces rather than direct logging calls. Probes are defined as Python Protocols, implemented with structlog, and bound with request-scoped context for correlation.

## Requirements

### Requirement: Probe Protocol Pattern
The system SHALL define observability as Protocol interfaces with domain-meaningful method names.

#### Scenario: Domain probe
- GIVEN a bounded context with business operations (e.g., tenant creation)
- THEN a probe Protocol exists with methods named after domain events (e.g., `tenant_created`, `tenant_deleted`)
- AND domain code depends only on the Protocol, not on structlog or any logging library

#### Scenario: Default implementation
- GIVEN a probe Protocol
- THEN a `DefaultXxxProbe` class exists that implements it using structlog
- AND log events use snake_case names matching domain semantics

### Requirement: Observation Context
The system SHALL propagate request-scoped metadata through probes via an immutable context object.

#### Scenario: Context binding
- GIVEN an ObservationContext with request_id, user_id, and tenant_id
- WHEN a probe is created with `probe.with_context(context)`
- THEN all subsequent log events include the context metadata

#### Scenario: Context immutability
- GIVEN an ObservationContext
- WHEN a caller attempts to mutate it
- THEN the mutation is rejected (frozen dataclass)

#### Scenario: Context enrichment
- GIVEN an existing ObservationContext
- WHEN `with_extra(key=value)` is called
- THEN a new context is returned with the additional metadata
- AND the original context is unchanged

#### Scenario: Selective inclusion
- GIVEN an ObservationContext with some None fields
- WHEN `as_dict()` is called
- THEN only non-None fields are included in the output

### Requirement: Probe Layering
The system SHALL define probes at each DDD layer with appropriate scope.

#### Scenario: Domain probes
- GIVEN the domain layer of a bounded context
- THEN probes capture aggregate-level events (e.g., member added, entity created)

#### Scenario: Application probes
- GIVEN the application layer of a bounded context
- THEN probes capture service-level events (e.g., permission denied, cascade started, operation completed)

#### Scenario: Infrastructure probes
- GIVEN the infrastructure layer
- THEN probes capture technical events (e.g., connection established, query executed, repository saved)

### Requirement: Structured Logging Configuration
The system SHALL configure structlog with environment-aware output formatting.

#### Scenario: Development environment
- GIVEN a development environment (TTY or FORCE_COLOR=1)
- THEN log output uses colored console rendering

#### Scenario: Production environment
- GIVEN a production environment (no TTY)
- THEN log output uses JSON rendering for structured log aggregation
