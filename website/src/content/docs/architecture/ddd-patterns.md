---
title: DDD Patterns in Kartograph
description: How Domain-Driven Design patterns are applied throughout the codebase
---

## Overview

Kartograph applies Domain-Driven Design (DDD) patterns consistently across all bounded contexts. This page documents the key patterns and where to find them in the codebase.

## Layered Architecture

Each bounded context follows a consistent layering:

```
api/
  context_name/
    domain/           # Pure domain logic, no dependencies
    application/      # Use cases, orchestrates domain
    infrastructure/   # Adapters, database, external services
    interface/        # HTTP, CLI, MCP endpoints
```

### Domain Layer

**Rules:**
- No dependencies on other layers
- Pure Python (no framework imports)
- Contains Entities, Value Objects, Domain Services

**Example:**
```python
# api/graph/domain/node.py
@dataclass
class Node:
    """Pure domain entity - no database dependencies."""
    id: NodeId
    label: str
    properties: dict[str, Any]

    def validate(self) -> None:
        """Domain validation rules."""
        if not self.label:
            raise ValueError("Node must have a label")
```

### Application Layer

**Rules:**
- Orchestrates domain objects
- Contains use cases (commands/queries)
- Depends on domain, not infrastructure

**Example:**
```python
# api/graph/application/apply_mutations.py
class ApplyMutationsUseCase:
    """Application service - orchestrates domain logic."""

    def __init__(self, repository: GraphRepository):
        self._repository = repository

    def execute(self, mutations: list[MutationOperation]) -> MutationResult:
        """Execute mutation operations in a transaction."""
        with self._repository.transaction():
            for mutation in mutations:
                self._apply_single_mutation(mutation)
```

### Infrastructure Layer

**Rules:**
- Implements interfaces defined in domain/application
- Database, file system, external APIs
- Never imported by domain layer

**Example:**
```python
# api/graph/infrastructure/age_repository.py
class AgeGraphRepository(GraphRepository):
    """Concrete implementation using Apache AGE."""

    def __init__(self, connection: Connection):
        self._conn = connection
```

## Key DDD Patterns

### Entities

Objects with identity that persist over time.

```python
# api/identity/domain/user.py
@dataclass
class User:
    """User entity - has identity, mutable state."""
    id: UserId
    email: Email
    name: str
    created_at: datetime

    def change_email(self, new_email: Email) -> None:
        """Business logic for email change."""
        self.email = new_email
```

### Value Objects

Immutable objects defined by their attributes.

```python
# api/graph/domain/value_objects.py
@dataclass(frozen=True)
class NodeId:
    """Value object - immutable, equality by value."""
    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("NodeId cannot be empty")
```

### Aggregates

Cluster of entities treated as a single unit.

```python
# api/management/domain/knowledge_graph.py
class KnowledgeGraph:
    """Aggregate root - controls access to data sources."""

    def __init__(self, id: KnowledgeGraphId, name: str):
        self._id = id
        self._name = name
        self._data_sources: list[DataSource] = []

    def add_data_source(self, data_source: DataSource) -> None:
        """Aggregate enforces invariants."""
        if data_source in self._data_sources:
            raise ValueError("Data source already exists")
        self._data_sources.append(data_source)
```

### Repositories

Abstraction for accessing aggregates.

```python
# api/graph/domain/repository.py
class GraphRepository(ABC):
    """Repository interface - defined in domain."""

    @abstractmethod
    def find_node_by_id(self, node_id: NodeId) -> Node | None:
        """Find a node by its ID."""
        pass

    @abstractmethod
    def save(self, node: Node) -> None:
        """Persist a node."""
        pass
```

### Domain Services

Operations that don't belong to a single entity.

```python
# api/graph/domain/id_generator.py
class GraphIdGenerator:
    """Domain service - pure logic, no state."""

    def generate_id(
        self,
        entity_type: str,
        slug: str,
        graph_id: str,
        secret: str
    ) -> str:
        """Generate cryptographically-scoped ID."""
        input_string = f"{entity_type}:{slug}:{graph_id}"
        hash_value = hmac.new(
            secret.encode(),
            input_string.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        return f"{entity_type.lower()}:{hash_value}"
```

### Domain Events

Things that happened in the domain.

```python
# api/extraction/domain/events.py
@dataclass(frozen=True)
class MutationLogCreated:
    """Domain event - something that happened."""
    mutation_log_id: str
    graph_id: str
    operation_count: int
    occurred_at: datetime
```

## Testing Patterns

### Domain Tests (Unit)

Test pure domain logic in isolation:

```python
# tests/unit/graph/domain/test_node.py
def test_node_validation():
    """Domain logic test - no dependencies."""
    with pytest.raises(ValueError):
        Node(id=NodeId("n1"), label="", properties={})
```

### Application Tests (Integration)

Test use cases with real dependencies:

```python
# tests/integration/graph/test_apply_mutations.py
def test_apply_mutations_creates_node(graph_repository):
    """Integration test - uses real repository."""
    use_case = ApplyMutationsUseCase(graph_repository)

    mutations = [
        {"op": "CREATE", "type": "node", ...}
    ]

    result = use_case.execute(mutations)
    assert result.success
```

### Architecture Tests

Enforce DDD boundaries:

```python
# tests/architecture/test_dependencies.py
def test_domain_has_no_infrastructure_dependencies():
    """Domain layer must be pure."""
    assert not imports(
        "api.*.domain.*",
        "api.*.infrastructure.*"
    )
```

## Next Steps

- Explore [Bounded Contexts](/architecture/bounded-contexts/) to see DDD in action
- Read [Extraction → Graph Mutations](/guides/extraction-mutations/) for a real-world interface
