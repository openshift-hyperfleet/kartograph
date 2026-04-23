---
id: task-027
title: Add canonical hash input and SHA256 verification tests for entity ID generation
spec_ref: specs/shared-kernel/entity-id-generation.spec.md@2683ffba25b66fc4e578e8b4703dd75224f80892
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Context

The `EntityIdGenerator` implementation is correct and extensive behavioral tests
exist in `tests/unit/shared_kernel/graph_primitives/test_entity_id_generator.py`.
However, two spec requirements lack tests that verify the **exact** canonical input
format and hashing algorithm:

**Requirement: Canonical Hash Input**
- Scenario: Node hash input — `{tenant_id}:{entity_type}:{entity_slug}`
- Scenario: Edge hash input — `{tenant_id}:{start_id}:{edge_type}:{end_id}`

**Requirement: SHA256-Based Hashing**
- Scenario: Hash derivation — first 16 chars of SHA256 hex digest

Without these tests, a change to the separator, field ordering, or hash algorithm
would not be caught — yet such a change would silently break ID compatibility
across ingestion runs (the whole purpose of deterministic IDs).

## Work Required

Add the following tests to `tests/unit/shared_kernel/graph_primitives/test_entity_id_generator.py`:

1. **`test_node_canonical_hash_input_format`** — Given known inputs (tenant_id,
   entity_type, entity_slug), independently compute
   `sha256(f"{tenant_id}:{entity_type}:{entity_slug}".encode()).hexdigest()[:16]`
   and assert `EntityIdGenerator.generate(...)` produces `{entity_type}:{expected_hash}`.

2. **`test_edge_canonical_hash_input_format`** — Given known inputs (tenant_id,
   start_id, edge_type, end_id), independently compute
   `sha256(f"{tenant_id}:{start_id}:{edge_type}:{end_id}".encode()).hexdigest()[:16]`
   and assert `EntityIdGenerator.generate_edge_id(...)` produces
   `{edge_type}:{expected_hash}`.

These tests serve as a regression contract: if the canonical format or algorithm
changes, they fail immediately, preventing silent ID drift.

## Spec Scenarios Addressed

- Requirement: Canonical Hash Input → Scenario: Node hash input
- Requirement: Canonical Hash Input → Scenario: Edge hash input
- Requirement: SHA256-Based Hashing → Scenario: Hash derivation (verified implicitly
  by the exact SHA256 computation in both tests above)
