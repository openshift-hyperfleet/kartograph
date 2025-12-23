# Database Migrations

This directory contains Alembic database migrations for Kartograph.

## Migration Workflow

### Creating a New Migration

Generate a new migration after modifying SQLAlchemy models:

```bash
# Auto-generate migration from model changes
cd src/api
uv run alembic revision --autogenerate -m "description of changes"
```

**Important**: Always review auto-generated migrations before applying them. Alembic may not detect all changes (e.g., column type changes, constraints).

### Running Migrations

Apply pending migrations to the database:

```bash
# Upgrade to latest version
uv run alembic upgrade head

# Upgrade to specific revision
uv run alembic upgrade <revision_id>
```

### Rolling Back Migrations

Downgrade to a previous migration:

```bash
# Downgrade one revision
uv run alembic downgrade -1

# Downgrade to specific revision
uv run alembic downgrade <revision_id>
```

### Checking Migration Status

```bash
# Show current revision
uv run alembic current

# Show migration history
uv run alembic history

# Show pending migrations
uv run alembic heads
```

## ULID Conventions

Kartograph uses ULIDs (Universally Unique Lexicographically Sortable Identifiers) for primary keys:

- **Type**: `String(26)` in SQLAlchemy
- **Format**: 26-character case-insensitive string (e.g., `01ARZ3NDEKTSV4RRFFQ69G5FAV`)
- **Advantages**: Time-ordered, URL-safe, more compact than UUIDs
- **Foreign Keys**: Also use `String(26)` when referencing ULID primary keys

Example:
```python
sa.Column("id", sa.String(length=26), nullable=False)  # ULID
sa.Column("workspace_id", sa.String(length=26), nullable=False)  # ULID FK
```

## Async Migration Considerations

Kartograph uses async SQLAlchemy with asyncpg, but Alembic migrations run **synchronously**:

- The migration `env.py` wraps async operations for compatibility
- Migrations use standard Alembic operations (`op.create_table`, etc.)
- Connection URL uses `postgresql+asyncpg://` but runs in sync context
- Do NOT use async/await in migration `upgrade()`/`downgrade()` functions

## Naming Conventions

### Migration Files

Migration files use Alembic's revision ID + descriptive name:
```text
<revision_id>_<description>.py
```

Examples:
- `7fbe65eaef1b_create_teams_table.py`
- `a1b2c3d4e5f6_add_user_email_index.py`

### Database Objects

Follow these naming conventions in migrations:

**Tables**: Plural, snake_case
```python
"teams", "workspaces", "api_keys"
```

**Indexes**: Use `op.f()` for automatic naming
```python
op.create_index(op.f("ix_teams_workspace_id"), "teams", ["workspace_id"])
# Creates: ix_teams_workspace_id
```

**Foreign Keys**: `fk_<table>_<column>_<referenced_table>`
```python
op.create_foreign_key(
    "fk_teams_workspace_id_workspaces",
    "teams", "workspaces",
    ["workspace_id"], ["id"]
)
```

**Unique Constraints**: `uq_<table>_<columns>`
```python
op.create_unique_constraint(
    "uq_teams_workspace_id_name",
    "teams",
    ["workspace_id", "name"]
)
```

## Best Practices

1. **Test migrations both ways**: Always test both `upgrade` and `downgrade`
2. **Keep migrations small**: One logical change per migration
3. **Data migrations**: Separate schema changes from data migrations when possible
4. **Production safety**: Test migrations against production-like data volumes
5. **Timestamps**: Use `DateTime(timezone=True)` for all timestamp columns
6. **NOT NULL defaults**: When adding NOT NULL columns to existing tables, provide server defaults
