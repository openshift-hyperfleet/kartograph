# Graph Vertical Slice Implementation Plan

## Overview

This document provides a comprehensive plan for implementing the Graph bounded context's vertical slice in the Kartograph modular monolith. The implementation follows Domain-Driven Design (DDD), Test-Driven Development (TDD), and the tracer bullet approach.

## Context

The Graph bounded context is responsible for:
- Applying mutation operations to the graph database (writes)
- Providing read-only access to the graph for other contexts
- Managing database integrity (cascade deletes, transactions)
- Enforcing security scoping via `data_source_id`

## Architectural Interface: JSONL Mutation Format

The mutation format is the **key architectural contract** between the Extraction and Graph contexts. Extraction produces JSONL files, Graph consumes them.

### Agreed Mutation Operation Schema

```python
class MutationOperation(BaseModel):
    """JSONL mutation operation.

    Semantics:
    - CREATE: Idempotent (uses MERGE). Creates if not exists, updates if exists.
    - UPDATE: Partial update. Use set_properties to add/change, remove_properties to remove.
    - DELETE: Cascades edges automatically (DETACH DELETE).
    """
    op: Literal["CREATE", "UPDATE", "DELETE"]
    type: Literal["node", "edge"]
    id: str  # Deterministic ID from Extraction context
    label: str | None = None  # Required for CREATE
    start_id: str | None = None  # Required for CREATE edge
    end_id: str | None = None  # Required for CREATE edge
    set_properties: dict[str, Any] | None = None  # For CREATE/UPDATE
    remove_properties: list[str] | None = None  # For UPDATE only (Option B)

    @model_validator(mode="after")
    def validate_operation(self):
        if self.op == "CREATE" and not self.label:
            raise ValueError("CREATE requires 'label'")
        if self.op == "CREATE" and self.type == "edge":
            if not self.start_id or not self.end_id:
                raise ValueError("CREATE edge requires 'start_id' and 'end_id'")
        if self.op == "CREATE":
            if not self.set_properties:
                raise ValueError("CREATE requires 'set_properties'")
            if "data_source_id" not in self.set_properties:
                raise ValueError("CREATE requires 'data_source_id'")
            if "source_path" not in self.set_properties:
                raise ValueError("CREATE requires 'source_path'")
        return self

class MutationResult(BaseModel):
    """Result of applying a batch of mutations."""
    success: bool
    operations_applied: int
    errors: list[str] = []
```

### Example JSONL Mutations

```jsonl
{"op": "CREATE", "type": "node", "id": "person:abc123", "label": "Person", "set_properties": {"slug": "alice-smith", "name": "Alice Smith", "data_source_id": "ds-456", "source_path": "people/alice.md"}}
{"op": "CREATE", "type": "edge", "id": "knows:xyz789", "label": "KNOWS", "start_id": "person:abc123", "end_id": "person:def456", "set_properties": {"since": 2020, "data_source_id": "ds-456", "source_path": "people/alice.md"}}
{"op": "UPDATE", "type": "node", "id": "person:abc123", "set_properties": {"name": "Alice Updated"}, "remove_properties": ["middle_name"]}
{"op": "DELETE", "type": "node", "id": "person:obsolete123"}
```

### Operation Semantics

#### CREATE
- **Idempotent**: Uses `MERGE` to create or update
- **Required fields**: `label`, `set_properties` with `data_source_id` and `source_path`
- **Edges**: Also requires `start_id` and `end_id`
- **Cypher pattern**:
  ```cypher
  MERGE (n:Person {id: 'person:abc123'})
  SET n.slug = 'alice-smith', n.name = 'Alice Smith', n.data_source_id = 'ds-456', n.source_path = 'people/alice.md'
  ```

#### UPDATE
- **Partial update**: Only changes specified properties
- **Option B**: Separate `set_properties` and `remove_properties` fields
- **Cypher pattern**:
  ```cypher
  MATCH (n {id: 'person:abc123'})
  SET n.name = 'Alice Updated'
  REMOVE n.middle_name
  ```

#### DELETE
- **Cascade edges**: Uses `DETACH DELETE` to automatically remove relationships
- **Cypher pattern**:
  ```cypher
  MATCH (n {id: 'person:obsolete123'})
  DETACH DELETE n
  ```

## Implementation Order (TDD)

### Phase 1: Domain Layer
**File**: `src/api/graph/domain/value_objects.py`

1. **Add to existing file** (already has NodeRecord, EdgeRecord, QueryResultRow)
2. Add `MutationOperation` with validation
3. Add `MutationResult`

**Tests**: `tests/unit/graph/test_value_objects.py`
- Test MutationOperation validation (CREATE requires label, etc.)
- Test edge creation requires start_id/end_id
- Test CREATE requires data_source_id and source_path
- Test model serialization/deserialization

### Phase 2: Infrastructure Layer - MutationApplier
**File**: `src/api/graph/infrastructure/mutation_applier.py`

```python
"""Mutation applier for Graph bounded context.

Applies mutation operations to the graph database in transactional batches.
Uses Domain-Oriented Observability for tracking.
"""

from graph.domain.value_objects import MutationOperation, MutationResult
from graph.infrastructure.protocols import GraphClientProtocol
from infrastructure.observability.probes import MutationProbe


class MutationApplier:
    """Applies mutation operations to the graph database.

    All operations are applied within a transaction for atomicity.
    Uses Domain-Oriented Observability for tracking.
    """

    def __init__(
        self,
        client: GraphClientProtocol,
        probe: MutationProbe | None = None,
    ):
        self._client = client
        self._probe = probe or DefaultMutationProbe()

    def apply_batch(
        self,
        operations: list[MutationOperation],
    ) -> MutationResult:
        """Apply a batch of mutations atomically.

        Args:
            operations: List of mutation operations to apply.

        Returns:
            MutationResult with success status and operation count.

        Raises:
            GraphQueryError: If any operation fails (transaction rolls back).
        """
        try:
            with self._client.transaction() as tx:
                for op in operations:
                    query = self._build_query(op)
                    tx.execute_cypher(query)
                    self._probe.mutation_applied(
                        operation=op.op,
                        entity_type=op.type,
                        entity_id=op.id,
                    )

            return MutationResult(
                success=True,
                operations_applied=len(operations),
            )
        except Exception as e:
            return MutationResult(
                success=False,
                operations_applied=0,
                errors=[str(e)],
            )

    def _build_query(self, op: MutationOperation) -> str:
        """Build Cypher query for mutation operation."""
        if op.op == "CREATE":
            return self._build_create(op)
        elif op.op == "UPDATE":
            return self._build_update(op)
        elif op.op == "DELETE":
            return self._build_delete(op)
        else:
            raise ValueError(f"Unknown operation: {op.op}")

    def _build_create(self, op: MutationOperation) -> str:
        """Build CREATE query using MERGE for idempotency."""
        if op.type == "node":
            # MERGE on id, set all properties
            props = ", ".join(
                f"n.{k} = {self._format_value(v)}"
                for k, v in (op.set_properties or {}).items()
            )
            return f"MERGE (n:{op.label} {{id: '{op.id}'}}) SET {props}"
        else:  # edge
            # MERGE on id, match start/end nodes, set properties
            props = ", ".join(
                f"r.{k} = {self._format_value(v)}"
                for k, v in (op.set_properties or {}).items()
            )
            return f"""
                MATCH (start {{id: '{op.start_id}'}})
                MATCH (end {{id: '{op.end_id}'}})
                MERGE (start)-[r:{op.label} {{id: '{op.id}'}}]->(end)
                SET {props}
            """

    def _build_update(self, op: MutationOperation) -> str:
        """Build UPDATE query with separate SET and REMOVE."""
        parts = [f"MATCH (n {{id: '{op.id}'}})"]

        if op.set_properties:
            set_clause = ", ".join(
                f"n.{k} = {self._format_value(v)}"
                for k, v in op.set_properties.items()
            )
            parts.append(f"SET {set_clause}")

        if op.remove_properties:
            remove_clause = ", ".join(f"n.{k}" for k in op.remove_properties)
            parts.append(f"REMOVE {remove_clause}")

        return " ".join(parts)

    def _build_delete(self, op: MutationOperation) -> str:
        """Build DELETE query with cascade (DETACH)."""
        return f"MATCH (n {{id: '{op.id}'}}) DETACH DELETE n"

    def _format_value(self, value: Any) -> str:
        """Format Python value for Cypher query."""
        if isinstance(value, str):
            return f"'{value}'"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif value is None:
            return "null"
        else:
            return str(value)
```

**Tests**: `tests/unit/graph/infrastructure/test_mutation_applier.py`
- Test CREATE node builds correct MERGE query
- Test CREATE edge builds correct MERGE with start/end match
- Test UPDATE with set_properties builds SET clause
- Test UPDATE with remove_properties builds REMOVE clause
- Test UPDATE with both set and remove
- Test DELETE builds DETACH DELETE
- Test batch applies all operations in transaction
- Test batch failure rolls back (mock transaction exception)

**Tests**: `tests/integration/graph/test_mutation_applier_integration.py`
- Test CREATE node actually creates in database
- Test CREATE is idempotent (run twice, verify single node)
- Test CREATE edge requires existing nodes
- Test UPDATE modifies properties
- Test UPDATE removes properties
- Test DELETE removes node and cascades edges
- Test batch transaction atomicity (all succeed or all fail)

### Phase 3: Application Layer - Services
**File**: `src/api/graph/application/services.py`

```python
"""Application services for Graph bounded context.

Orchestrates business logic and coordinates between domain and infrastructure.
"""

from graph.domain.value_objects import (
    EdgeRecord,
    MutationOperation,
    MutationResult,
    NodeRecord,
    QueryResultRow,
)
from graph.infrastructure.mutation_applier import MutationApplier
from graph.ports.repositories import IGraphReadOnlyRepository


class GraphQueryService:
    """Service for querying the graph (read operations).

    Provides a clean interface for other contexts to query graph data
    without depending on infrastructure details.
    """

    def __init__(self, repository: IGraphReadOnlyRepository):
        self._repository = repository

    def find_entities_by_path(
        self,
        path: str,
    ) -> tuple[list[NodeRecord], list[EdgeRecord]]:
        """Find nodes and edges by source file path.

        Args:
            path: Source file path (e.g., "people/alice.md").

        Returns:
            Tuple of (nodes, edges) found at that path.
        """
        return self._repository.find_nodes_by_path(path)

    def find_entities_by_slug(
        self,
        slug: str,
        node_type: str | None = None,
    ) -> list[NodeRecord]:
        """Find nodes by their slug.

        Args:
            slug: Entity slug (e.g., "alice-smith").
            node_type: Optional type filter (e.g., "Person").

        Returns:
            List of matching nodes.
        """
        return self._repository.find_nodes_by_slug(slug, node_type)

    def get_neighbors(
        self,
        node_id: str,
    ) -> tuple[list[NodeRecord], list[EdgeRecord]]:
        """Get neighboring nodes and connecting edges.

        Args:
            node_id: The node ID to find neighbors for.

        Returns:
            Tuple of (neighbor_nodes, edges).
        """
        return self._repository.get_neighbors(node_id)

    def execute_exploration_query(
        self,
        query: str,
        timeout_seconds: int = 5,
    ) -> list[QueryResultRow]:
        """Execute a custom read-only query for exploration.

        Args:
            query: Cypher query string.
            timeout_seconds: Query timeout (default 5s).

        Returns:
            List of result rows as dictionaries.

        Raises:
            GraphQueryError: If query is invalid or times out.
        """
        return self._repository.execute_raw_query(query, timeout_seconds)


class GraphMutationService:
    """Service for mutating the graph (write operations).

    This is the primary interface for applying mutation operations
    from the Extraction context.
    """

    def __init__(self, applier: MutationApplier):
        self._applier = applier

    def apply_mutations(
        self,
        operations: list[MutationOperation],
    ) -> MutationResult:
        """Apply a batch of mutation operations atomically.

        Args:
            operations: List of mutations to apply.

        Returns:
            MutationResult with success status and counts.
        """
        return self._applier.apply_batch(operations)

    def apply_mutations_from_jsonl(
        self,
        jsonl_content: str,
    ) -> MutationResult:
        """Apply mutations from JSONL string.

        Args:
            jsonl_content: JSONL string with one operation per line.

        Returns:
            MutationResult with success status and counts.

        Raises:
            ValueError: If JSONL is malformed.
        """
        operations = []
        for line in jsonl_content.strip().split("\n"):
            if line:
                op_dict = json.loads(line)
                operations.append(MutationOperation(**op_dict))

        return self.apply_mutations(operations)
```

**Tests**: `tests/unit/graph/application/test_services.py`
- Test GraphQueryService delegates to repository correctly
- Test GraphMutationService delegates to applier correctly
- Test apply_mutations_from_jsonl parses JSONL correctly
- Test apply_mutations_from_jsonl handles malformed JSONL

### Phase 4: Presentation Layer - HTTP Routes
**File**: `src/api/graph/presentation/routes.py`

```python
"""HTTP routes for Graph bounded context.

Provides REST API for manual testing and future external integrations.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from graph.application.services import GraphMutationService, GraphQueryService
from graph.domain.value_objects import MutationOperation, MutationResult

router = APIRouter(prefix="/graph", tags=["graph"])


# Dependency injection
def get_query_service() -> GraphQueryService:
    """Get GraphQueryService instance."""
    # TODO: Implement proper DI with client injection
    raise NotImplementedError("DI not yet configured")


def get_mutation_service() -> GraphMutationService:
    """Get GraphMutationService instance."""
    # TODO: Implement proper DI with client injection
    raise NotImplementedError("DI not yet configured")


@router.post("/mutations", status_code=status.HTTP_200_OK)
async def apply_mutations(
    operations: list[MutationOperation],
    service: Annotated[GraphMutationService, Depends(get_mutation_service)],
) -> MutationResult:
    """Apply a batch of mutation operations.

    Request body should be a JSON array of mutation operations.

    Example:
        [
            {
                "op": "CREATE",
                "type": "node",
                "id": "person:abc123",
                "label": "Person",
                "set_properties": {
                    "slug": "alice-smith",
                    "name": "Alice Smith",
                    "data_source_id": "ds-456",
                    "source_path": "people/alice.md"
                }
            }
        ]
    """
    result = service.apply_mutations(operations)
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errors": result.errors},
        )
    return result


@router.get("/nodes/by-path")
async def find_by_path(
    path: str,
    service: Annotated[GraphQueryService, Depends(get_query_service)],
) -> dict:
    """Find nodes and edges by source file path.

    Query parameter:
        path: Source file path (e.g., "people/alice.md")

    Returns:
        {
            "nodes": [...],
            "edges": [...]
        }
    """
    nodes, edges = service.find_entities_by_path(path)
    return {
        "nodes": [n.model_dump() for n in nodes],
        "edges": [e.model_dump() for e in edges],
    }


@router.get("/nodes/by-slug")
async def find_by_slug(
    slug: str,
    node_type: str | None = None,
    service: Annotated[GraphQueryService, Depends(get_query_service)],
) -> dict:
    """Find nodes by slug.

    Query parameters:
        slug: Entity slug (e.g., "alice-smith")
        node_type: Optional type filter (e.g., "Person")

    Returns:
        {
            "nodes": [...]
        }
    """
    nodes = service.find_entities_by_slug(slug, node_type)
    return {"nodes": [n.model_dump() for n in nodes]}


@router.get("/nodes/{node_id}/neighbors")
async def get_neighbors(
    node_id: str,
    service: Annotated[GraphQueryService, Depends(get_query_service)],
) -> dict:
    """Get neighboring nodes and connecting edges.

    Path parameter:
        node_id: The node ID to find neighbors for

    Returns:
        {
            "nodes": [...],
            "edges": [...]
        }
    """
    nodes, edges = service.get_neighbors(node_id)
    return {
        "nodes": [n.model_dump() for n in nodes],
        "edges": [e.model_dump() for e in edges],
    }
```

**Tests**: `tests/integration/graph/presentation/test_routes.py`
- Test POST /graph/mutations with valid operations
- Test POST /graph/mutations with invalid operations (400)
- Test POST /graph/mutations with mutation failure (500)
- Test GET /graph/nodes/by-path
- Test GET /graph/nodes/by-slug
- Test GET /graph/nodes/{node_id}/neighbors

### Phase 5: Wire Up Dependency Injection
**File**: `src/api/main.py` (update existing)

Add the following dependency providers:

```python
@lru_cache
def get_mutation_applier() -> MutationApplier:
    """Get a cached MutationApplier instance."""
    client = get_graph_client()
    return MutationApplier(client=client)


def get_graph_mutation_service(
    applier: Annotated[MutationApplier, Depends(get_mutation_applier)],
) -> GraphMutationService:
    """Get a GraphMutationService instance."""
    return GraphMutationService(applier=applier)


# Update existing get_graph_query_service to return GraphQueryService
def get_graph_query_service(
    client: Annotated[AgeGraphClient, Depends(get_graph_client)],
) -> GraphQueryService:
    """Get a GraphQueryService instance."""
    if not client.is_connected():
        client.connect()

    repository = GraphExtractionReadOnlyRepository(
        client=client,
        data_source_id="default",  # TODO: Derive from request context
    )
    return GraphQueryService(repository=repository)
```

Update `graph/presentation/routes.py` to remove placeholder DI functions and import from main.

**Tests**: `tests/integration/test_main.py`
- Test DI creates services correctly
- Test services are properly wired

## Domain-Oriented Observability (DOO)

### Mutation Probe
**File**: `src/api/infrastructure/observability/probes.py`

```python
"""Domain probes for observability."""

from abc import ABC, abstractmethod


class MutationProbe(ABC):
    """Probe for tracking mutation operations."""

    @abstractmethod
    def mutation_applied(
        self,
        operation: str,
        entity_type: str,
        entity_id: str,
    ) -> None:
        """Record that a mutation was successfully applied."""
        pass


class DefaultMutationProbe(MutationProbe):
    """Default implementation using structured logging."""

    def mutation_applied(
        self,
        operation: str,
        entity_type: str,
        entity_id: str,
    ) -> None:
        """Record mutation in structured log."""
        # Use structured logging, not logger.info
        emit_domain_event(
            event_type="mutation_applied",
            operation=operation,
            entity_type=entity_type,
            entity_id=entity_id,
        )
```

## Testing Strategy

### Unit Tests
- **Domain**: Value object validation
- **Infrastructure**: Query building logic (mocked client)
- **Application**: Service delegation (mocked dependencies)
- **Presentation**: Route handling (mocked services)

### Integration Tests
- **Infrastructure**: Actual database operations against PostgreSQL/AGE
- **Presentation**: Full HTTP request/response cycle
- **End-to-End**: JSONL file → mutations → verify in database

### Test Data
Use consistent test data across all integration tests:
- Data source: `test-ds-integration`
- Person nodes: Alice Smith, Bob Jones
- Relationship: Alice KNOWS Bob since 2020

## Manual Testing with curl

### Create a node
```bash
curl -X POST http://localhost:8000/graph/mutations \
  -H "Content-Type: application/json" \
  -d '[{
    "op": "CREATE",
    "type": "node",
    "id": "person:alice123",
    "label": "Person",
    "set_properties": {
      "slug": "alice-smith",
      "name": "Alice Smith",
      "data_source_id": "ds-456",
      "source_path": "people/alice.md"
    }
  }]'
```

### Create an edge
```bash
curl -X POST http://localhost:8000/graph/mutations \
  -H "Content-Type: application/json" \
  -d '[{
    "op": "CREATE",
    "type": "edge",
    "id": "knows:xyz789",
    "label": "KNOWS",
    "start_id": "person:alice123",
    "end_id": "person:bob456",
    "set_properties": {
      "since": 2020,
      "data_source_id": "ds-456",
      "source_path": "people/alice.md"
    }
  }]'
```

### Update a node
```bash
curl -X POST http://localhost:8000/graph/mutations \
  -H "Content-Type: application/json" \
  -d '[{
    "op": "UPDATE",
    "type": "node",
    "id": "person:alice123",
    "set_properties": {"name": "Alice Updated"},
    "remove_properties": ["middle_name"]
  }]'
```

### Delete a node
```bash
curl -X POST http://localhost:8000/graph/mutations \
  -H "Content-Type: application/json" \
  -d '[{
    "op": "DELETE",
    "type": "node",
    "id": "person:obsolete123"
  }]'
```

### Query by path
```bash
curl "http://localhost:8000/graph/nodes/by-path?path=people/alice.md"
```

### Query by slug
```bash
curl "http://localhost:8000/graph/nodes/by-slug?slug=alice-smith&node_type=Person"
```

### Get neighbors
```bash
curl "http://localhost:8000/graph/nodes/person:alice123/neighbors"
```

## Implementation Checklist

- [ ] Phase 1: Add MutationOperation and MutationResult to value_objects.py
- [ ] Phase 1: Write unit tests for value object validation
- [ ] Phase 2: Implement MutationApplier in mutation_applier.py
- [ ] Phase 2: Write unit tests for query building
- [ ] Phase 2: Write integration tests for database operations
- [ ] Phase 3: Implement GraphQueryService and GraphMutationService
- [ ] Phase 3: Write unit tests for service delegation
- [ ] Phase 4: Implement HTTP routes in routes.py
- [ ] Phase 4: Write integration tests for routes
- [ ] Phase 5: Wire up dependency injection in main.py
- [ ] Phase 5: Write integration tests for DI
- [ ] Add MutationProbe for DOO
- [ ] Manual testing with curl commands
- [ ] Update CLAUDE.md if necessary

## Key Design Decisions

1. **JSONL Mutation Format**: Option B with separate `set_properties` and `remove_properties`
2. **CREATE Idempotency**: Uses `MERGE` for idempotent creates
3. **DELETE Cascade**: Uses `DETACH DELETE` to automatically remove edges
4. **Transaction Scope**: All mutations in a batch are applied atomically
5. **Security Scoping**: All operations require `data_source_id` in properties
6. **Timeout Enforcement**: Read queries have configurable timeouts
7. **Domain Probes**: Use structured events, not logger.* or print()

## Future Enhancements

- [ ] Add support for RENAME operations (UPDATE with id change)
- [ ] Add batch size limits and pagination for large mutation sets
- [ ] Add retry logic for transient database failures
- [ ] Add metrics for mutation throughput and latency
- [ ] Add support for conditional mutations (only update if condition met)
- [ ] Add support for graph schema validation
