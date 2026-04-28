---
task_id: audit-specs/management/knowledge-graphs.spec.md@85d49a379a52479b33f9b39994d76795066899a6
round: 0
role: auditor
verdict: fail
---
## Alignment Audit — specs/management/knowledge-graphs.spec.md

---

## Summary

The implementation is substantially aligned with the spec across most
requirements. All CRUD operations, permission enforcement, name validation,
ULID generation, duplicate detection, and permission-inheritance scenarios
are correctly implemented and tested. However, the spec contains an explicit
no-partial-state atomicity guarantee for deletion that the code violates when
data sources have encrypted credentials: `secret_store.delete()` runs outside
the PostgreSQL transaction, so a DB rollback after a successful credential
deletion leaves orphaned records.

---

## Gaps

### GAP 1 — FAIL: Deletion partial-state possible when credentials exist

**Spec requirement** ("Requirement: Knowledge Graph Deletion, Scenario: Successful deletion"):

> The following cascade executes atomically within a single transaction …
> AND if any step fails, the entire deletion rolls back with no partial state.

**Code location**:
`src/api/management/application/services/knowledge_graph_service.py` lines 403–418

```python
async with self._session.begin():
    if self._ds_repo is not None:
        data_sources = await self._ds_repo.find_by_knowledge_graph(kg_id)
        for ds in data_sources:
            if ds.credentials_path and self._secret_store is not None:
                await self._secret_store.delete(   # ← external call, NOT in DB txn
                    path=ds.credentials_path,
                    tenant_id=self._scope_to_tenant,
                )
            ds.mark_for_deletion(deleted_by=user_id)
            await self._ds_repo.delete(ds)        # ← in DB txn
    kg.mark_for_deletion(deleted_by=user_id)
    await self._kg_repo.delete(kg)
```

`secret_store.delete()` is invoked against an external system (e.g., Vault /
filesystem) before the corresponding DS row is removed from the DB. If a later
iteration raises (e.g., `secret_store.delete()` fails for a subsequent DS, or
a DB flush error occurs), `session.begin()` rolls back all DB changes, but any
credentials already deleted from the secret store are NOT restored.

**Concrete failure scenario**:
1. DS-1: `secret_store.delete(ds1_creds)` → succeeds (Vault entry gone)
2. DS-2: `secret_store.delete(ds2_creds)` → raises `NetworkError`
3. Exception propagates → `session.begin()` rolls back → DS-1 record is
   restored in DB, DS-2 record is untouched
4. **Result**: DS-1 record exists in DB, but its credentials are permanently
   deleted — partial state the spec prohibits.

**Recommended fix**: Move `secret_store.delete()` calls to **after** the DB
transaction commits (best-effort GC with idempotent retry), or use a
soft-delete flag to mark credentials for asynchronous cleanup.

---

### GAP 2 — Design gap: Authorization relationship cleanup is eventual, not atomic

**Spec requirement**: "All authorization relationships are cleaned up (workspace,
tenant, and all direct grants)" is listed as a step that must execute
"atomically within a single transaction."

**Code path**:
- `src/api/management/infrastructure/repositories/knowledge_graph_repository.py`
  lines 145–157: `delete()` writes a `KnowledgeGraphDeleted` outbox entry
  within the same DB transaction as the record deletion — durability is
  guaranteed.
- `src/api/management/infrastructure/outbox/translator.py` lines 160–211:
  `_translate_knowledge_graph_deleted()` produces five SpiceDB operations
  (delete workspace, tenant, admin, editor, viewer relationships), but these
  are executed **asynchronously** by the outbox worker, not within the
  deletion transaction.

If the outbox worker fails or is delayed, the DB records are gone but SpiceDB
retains orphaned relationship tuples. The content of the cleanup is correct;
only the atomicity guarantee diverges from the spec's language.

Note: The outbox entry is written in the same DB transaction, so eventual
consistency is guaranteed as long as the outbox worker eventually runs.

---

### GAP 3 — Minor: `list_for_workspace` is temporarily inconsistent with `get_by_id` for new KGs

**Spec**: "List for workspace … THEN only knowledge graphs the user can view
are returned."

`list_for_workspace()` discovers KG IDs via SpiceDB relationship tuples
(`read_relationships` for `workspace` relation). These tuples are written by
the outbox worker after processing `KnowledgeGraphCreated`. Until the outbox
fires, a newly created KG is accessible via `GET /knowledge-graphs/{id}` (DB
lookup) but absent from `GET /workspaces/{id}/knowledge-graphs` (SpiceDB
lookup).

**Code location**: `src/api/management/application/services/knowledge_graph_service.py`
lines 241–268 (`list_for_workspace()`).

This is an eventual-consistency window inherent to the outbox pattern; the
listing will be correct once the outbox processes the event.

---

## Aligned Requirements (all verified)

| Requirement | Scenario | Status |
|---|---|---|
| Creation | ULID generated, workspace + tenant stored in DB | ✅ |
| Creation | EDIT permission on workspace enforced | ✅ |
| Creation | Duplicate name within tenant rejected (409) | ✅ |
| Name Validation | 1–100 chars enforced at aggregate + Pydantic layer | ✅ |
| Name Validation | Empty or oversized name rejected | ✅ |
| Retrieval | VIEW permission checked; None returned if missing | ✅ |
| Retrieval | No existence leakage (unauthorized = same as not found) | ✅ |
| Listing | Workspace VIEW check; SpiceDB relationship discovery | ✅ |
| Update | EDIT permission on KG enforced | ✅ |
| Update | Name/description updated; duplicate name → 409 | ✅ |
| Deletion | MANAGE permission on KG enforced | ✅ |
| Deletion | Data sources cascade-deleted in same DB transaction | ✅ |
| Deletion | Credentials deleted via secret store | ✅ (but see GAP 1) |
| Deletion | SpiceDB auth cleanup (workspace, tenant, direct grants) | ✅ (eventual, see GAP 2) |
| Mutation after deletion | Aggregate raises AggregateDeletedError; service returns 404 | ✅ |
| Permission inheritance | workspace→KG VIEW/EDIT/MANAGE chains tested | ✅ |
| Direct grant | admin on KG → manage+edit+view; verified in integration tests | ✅ |