---
id: task-010
title: Enforce database-level read-only session for graph queries
spec_ref: specs/query/query-execution.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## What

Add `SET TRANSACTION READ ONLY` (or equivalent) to every query session in `QueryGraphRepository` so the database itself rejects write operations, independent of the application-level keyword blacklist.

## Spec gap

**Read-Only Enforcement — Database-level enforcement (primary):**
> - GIVEN a query session used for graph queries
> - WHEN any query is executed
> - THEN the database session MUST be configured as read-only
> - AND write attempts are rejected by the database regardless of query content

## Current state

`query/infrastructure/query_repository.py` — `QueryGraphRepository.execute_cypher()` only implements the keyword blacklist (secondary defense). It uses `SET LOCAL statement_timeout` within a transaction but does NOT set the transaction as read-only:

```python
with self._client.transaction() as tx:
    tx.execute_sql(f"SET LOCAL statement_timeout = {timeout_seconds * 1000}")
    result = tx.execute_cypher(query)
```

The keyword blacklist alone is insufficient per the spec — it is the secondary defense. The database-level enforcement is the primary defense.

## Required changes

1. Before executing the Cypher query, issue `SET TRANSACTION READ ONLY` (or `SET LOCAL transaction_read_only = on`) within the same transaction.
2. Write a unit test confirming the `SET TRANSACTION READ ONLY` statement is issued.
3. Write an integration test confirming that a write-keyword query that bypasses the blacklist (e.g., by escaping) is still rejected at the database level.

## Notes

- For Apache AGE, `SET TRANSACTION READ ONLY` must be issued after `BEGIN` but before the first query — the transaction context manager in `AgeGraphClient` is the right place.
- Alternatively, add a `read_only=True` parameter to the `transaction()` context manager and set `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` or use `psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED` with read-only flag.
- The correlation ID on timeout errors (also in this spec) should be verified — check if `QueryTimeoutError` already includes a correlation ID.
