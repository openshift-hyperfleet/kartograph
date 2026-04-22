# Bulk Loading

## Purpose
Bulk loading optimizes high-throughput graph ingestion by bypassing Cypher MERGE in favor of direct PostgreSQL operations (COPY protocol, direct SQL). This is the performance-critical path for large mutation batches.

NFR: This spec describes a performance optimization strategy, not domain behavior. The behavioral contract for mutations is defined in [mutations.spec.md](mutations.spec.md).

## Requirements

### Requirement: Operation Partitioning
The system SHALL partition mutation operations by type and enforce referential integrity ordering.

#### Scenario: Mixed operation batch
- GIVEN a batch with CREATE, DELETE, and UPDATE operations for nodes and edges
- WHEN the batch is processed
- THEN DELETEs execute first (edges before nodes)
- AND CREATEs execute next (nodes before edges)
- AND UPDATEs execute last

### Requirement: Label and Index Pre-Creation
The system SHALL create graph labels and performance indexes before bulk-inserting data.

#### Scenario: New label in batch
- GIVEN a CREATE operation for a label that does not yet exist in the graph
- WHEN the batch is processed
- THEN the label table is created before data insertion
- AND indexes are created on the new label table

### Requirement: Staging-Based Ingestion
The system SHALL use temporary staging tables and PostgreSQL COPY for efficient data loading.

#### Scenario: Node bulk create
- GIVEN a batch of node CREATE operations
- WHEN the batch is processed
- THEN data is loaded into a temporary staging table via COPY
- AND staging data is merged into the graph via direct SQL (not Cypher)
- AND the staging table is dropped on commit

#### Scenario: Edge bulk create with ID resolution
- GIVEN a batch of edge CREATE operations referencing logical node IDs
- WHEN the batch is processed
- THEN a graphid lookup table is built from the union of pre-existing nodes and nodes created earlier in the same batch
- AND logical IDs are resolved to internal graph IDs via join against this lookup table
- AND edges are inserted with resolved graph IDs
- AND nodes from the same batch MUST be materialized (inserted into the graph) before the lookup table is built, so that edge endpoint resolution includes same-batch node IDs

### Requirement: Duplicate and Orphan Detection
The system SHALL detect data quality issues within a batch.

#### Scenario: Duplicate IDs in batch
- GIVEN a batch containing two CREATE operations with the same entity ID
- WHEN the batch is processed
- THEN the duplicates are detected and reported

#### Scenario: Orphaned edges
- GIVEN edge CREATE operations referencing node IDs that do not exist
- WHEN the batch is processed
- THEN the orphaned edges are detected and reported

### Requirement: Concurrency Safety
The system SHALL use advisory locks to prevent concurrent bulk loading conflicts on the same labels.

#### Scenario: Concurrent batches
- GIVEN two bulk loading operations targeting the same label
- WHEN both execute simultaneously
- THEN advisory locks ensure they do not conflict

#### Scenario: Deterministic lock ordering
- GIVEN a bulk loading operation that acquires locks on multiple labels
- WHEN advisory locks are acquired
- THEN labels MUST be sorted into a canonical order (e.g., alphabetical) before acquisition
- AND locks are acquired strictly in that order to prevent deadlocks
- AND if any lock acquisition fails, all previously acquired locks are released before retry
