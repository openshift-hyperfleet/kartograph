# Query Execution

## Purpose
Query execution translates Cypher queries into graph database operations with safety guardrails. It enforces read-only access via defense-in-depth (database-level and application-level controls), timeouts, and result limits to protect both the database and the consumer.

## Requirements

### Requirement: Read-Only Enforcement
The system SHALL enforce read-only query execution via defense-in-depth.

#### Scenario: Database-level enforcement (primary)
- GIVEN a query session used for graph queries
- WHEN any query is executed
- THEN the database session MUST be configured as read-only
- AND write attempts are rejected by the database regardless of query content

#### Scenario: Keyword blacklist (secondary)
- GIVEN a query containing any of: CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD
- WHEN the query is submitted (case-insensitive check)
- THEN it is rejected with a forbidden error before reaching the database
- AND a redacted reference is logged (not the raw query text)
- AND the error response includes a correlation ID for log lookup

### Requirement: Timeout Enforcement
The system SHALL enforce a per-query timeout at the database level.

#### Scenario: Query within timeout
- GIVEN a query that completes within the timeout
- WHEN the query executes
- THEN results are returned normally

#### Scenario: Query exceeds timeout
- GIVEN a query that takes longer than the timeout
- WHEN the database cancels the statement
- THEN a timeout error is returned with a correlation ID for debugging

### Requirement: Result Limiting
The system SHALL enforce a maximum number of returned rows.

#### Scenario: No LIMIT in query
- GIVEN a query without a LIMIT clause
- WHEN the query is executed
- THEN a LIMIT of 1000 is appended automatically

#### Scenario: Explicit LIMIT within bounds
- GIVEN a query with a LIMIT clause at or below 10000
- WHEN the query is executed
- THEN the existing LIMIT is respected

#### Scenario: Explicit LIMIT exceeds maximum
- GIVEN a query with a LIMIT clause exceeding 10000
- WHEN the query is executed
- THEN the LIMIT is capped to 10000

### Requirement: Error Categorization
The system SHALL categorize query errors into distinct types for consumer handling.

#### Scenario: Forbidden query
- GIVEN a query containing mutation keywords
- THEN the error type is "forbidden"

#### Scenario: Timeout error
- GIVEN a query that exceeds the timeout
- THEN the error type is "timeout"

#### Scenario: Execution error
- GIVEN a query with a syntax error or runtime failure
- THEN the error type is "execution_error"

#### Scenario: Unexpected error
- GIVEN an unexpected failure during query execution
- THEN the error type is "unknown_error"
