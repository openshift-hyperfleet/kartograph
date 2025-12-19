---
title: Bounded Contexts
description: The six bounded contexts that structure Kartograph
---

## Overview

Kartograph follows Domain-Driven Design with six distinct bounded contexts. Each context has a single, well-defined responsibility and communicates with others through explicit interfaces.

## The Six Contexts

### 1. Identity

**Purpose:** Manages "who" can do "what" (Authentication & Authorization)

**Responsibilities:**
- User, Team, and Tenant management
- API Key lifecycle management

**Key Entities:**
- `User`
- `Team`
- `Tenant`
- `APIKey`

### 2. Management

**Purpose:** The "Control Plane" for the platform. Manages metadata and configuration.

**Responsibilities:**
- CRUD operations for **KnowledgeGraph** and **DataSource** configurations
- Storing encrypted credentials (via Vault)
- Defining and managing synchronization schedules

**Key Entities:**
- `KnowledgeGraph`
- `DataSource`
- `SyncSchedule`

### 3. Ingestion

**Purpose:** Extracting raw data. This is where the **Adapters** (GitHub, K8s, etc.) live.

**Responsibilities:**
- Running adapters to fetch "Raw Content Changesets" (what changed?)
- Generating sync manifests
- Packaging raw content and manifests into **JobPackages** (Zip files) for processing

**Key Entities:**
- `Adapter`
- `RawContentChangeset`
- `SyncManifest`
- `JobPackage`

### 4. Extraction

**Purpose:** Transforming raw content into Graph Data. This is where the **AI Agent** lives.

**Responsibilities:**
- Processing JobPackages from Ingestion
- Running the **Claude Agent SDK** to determine relationships and entities
- Running the **Deterministic Processor** for non-AI tasks (renames/deletes)
- Producing a **MutationLog** (JSONL) of graph operations

**Key Entities:**
- `ExtractionAgent`
- `DeterministicProcessor`
- [`MutationLog`](../guides/extraction-mutations/) (JSONL file)


### 5. Graph

**Purpose:** The persistence engine. Executes writes and serves reads.

**Responsibilities:**
- Applying the **MutationLogs** to the database (Transactional Writes)
- Managing database integrity (e.g., cascading deletes)
- Exposing a safe, scoped, read-only API for the Extraction agent to "see" the existing graph during processing

**Key Entities:**
- `GraphDatabase`
- `Node`
- `Edge`
- `GraphExtractionReadOnlyRepository` (for Extraction context)

### 6. Querying

**Purpose:** The consumer interface. Provides read access to end-users and agents.

**Responsibilities:**
- Hosting the **MCP (Model Context Protocol) Server**
- Translating user/agent questions into database queries
- Enforcing rate limits and query complexity safety checks

**Key Entities:**
- `MCPServer`
- `QueryEngine`
- `RateLimiter`

## Context Boundaries

### Strict Rules

1. **No direct database access across contexts**
   - ❌ Ingestion cannot write to the graph database
   - ✅ Ingestion produces JobPackages, Graph reads them

2. **No shared domain models**
   - ❌ Don't import `Graph.Node` in Extraction
   - ✅ Use DTOs and value objects at boundaries

3. **Explicit interfaces**
   - ❌ Implicit dependencies via shared state
   - ✅ JSONL files, message queues, REST APIs

### Communication Patterns

```
Identity → Management: REST API (Auth tokens)
Management → Ingestion: Job scheduling (message queue)
Ingestion → Extraction: JobPackage (file system / S3)
Extraction → Graph: MutationLog JSONL (file system / S3)
Graph → Querying: Read-only database connection
Querying → Identity: Auth validation (REST API)
```

## Architectural Tests

Kartograph uses `pytest-archon` to enforce boundaries:

```python
# tests/architecture/test_bounded_contexts.py

def test_extraction_cannot_import_from_graph():
    """Extraction context must not import Graph domain models."""
    assert not imports(
        "api.extraction.*",
        "api.graph.domain.*"
    )

def test_ingestion_cannot_access_database():
    """Ingestion must not directly access graph database."""
    assert not imports(
        "api.ingestion.*",
        "api.graph.infrastructure.database"
    )
```

## Next Steps

- Learn about [DDD Patterns](../../architecture/ddd-patterns/) used in each context
