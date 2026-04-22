# Outbox

## Purpose
The outbox pattern ensures that domain events and their side effects (e.g., SpiceDB relationship writes) are eventually consistent. Events are stored in the same database transaction as the aggregate change, then processed asynchronously by a worker.

## Requirements

### Requirement: Transactional Event Storage
The system SHALL store domain events in the outbox table within the same database transaction as the aggregate mutation.

#### Scenario: Successful write
- GIVEN a service that modifies an aggregate (e.g., creates a tenant)
- WHEN the aggregate emits domain events
- THEN the events are serialized and appended to the outbox table
- AND the aggregate change and outbox entries commit or roll back together

#### Scenario: Transaction rollback
- GIVEN a service operation that fails after emitting events
- WHEN the transaction rolls back
- THEN no outbox entries are persisted
- AND no side effects occur

### Requirement: Event Processing
The system SHALL process outbox entries asynchronously via a worker.

#### Scenario: Normal processing
- GIVEN unprocessed outbox entries
- WHEN the worker picks them up
- THEN each entry is translated into authorization operations
- AND the operations are applied (e.g., SpiceDB relationship writes)
- AND the entry is marked as processed with a timestamp

#### Scenario: Transient failure
- GIVEN an outbox entry that fails to process (e.g., SpiceDB unreachable)
- WHEN the worker retries
- THEN the retry count is incremented
- AND the last error is recorded

#### Scenario: Permanent failure (dead letter)
- GIVEN an outbox entry that has exceeded the maximum retry count
- WHEN the worker encounters it
- THEN the entry is moved to a dead-letter state (failed_at timestamp set)
- AND it is no longer retried

### Requirement: Idempotent Event Handlers
The system SHALL ensure that event handlers are idempotent, tolerating duplicate delivery from retries or concurrent processing.

#### Scenario: Duplicate delivery
- GIVEN an outbox entry that was partially processed before a transient failure
- WHEN the worker retries the same entry
- THEN reprocessing produces the same final state as a single successful processing
- AND no duplicate side effects are created (e.g., duplicate SpiceDB relationships)

### Requirement: Concurrent Worker Safety
The system SHALL support multiple outbox workers processing entries without duplication.

#### Scenario: Concurrent workers
- GIVEN two workers polling for unprocessed entries simultaneously
- WHEN both query the outbox table
- THEN each entry is claimed by exactly one worker (via database row locking)
- AND no entry is processed twice

### Requirement: Dual Delivery Mechanism
The system SHALL use both real-time notification and polling to process outbox entries.

#### Scenario: Real-time notification
- GIVEN a new outbox entry is inserted
- WHEN a PostgreSQL NOTIFY is emitted
- THEN the worker processes the entry promptly (sub-second)

#### Scenario: Polling fallback
- GIVEN the NOTIFY mechanism misses an event (e.g., worker restart)
- WHEN the polling interval elapses (default 30 seconds)
- THEN the worker discovers and processes the missed entry

### Requirement: Event Fan-Out
The system SHALL support routing a single event type to multiple handlers.

#### Scenario: Multiple handlers registered
- GIVEN two handlers registered for the same event type
- WHEN an event of that type is processed
- THEN both handlers are invoked

#### Scenario: Unknown event type
- GIVEN an outbox entry with an unregistered event type
- WHEN the worker attempts to process it
- THEN the entry is immediately moved to the dead-letter state
- AND it is not retried (unknown types are permanent failures, not transient)
