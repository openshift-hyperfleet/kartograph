---
id: task-007
title: Fix advisory lock ordering in bulk loading to prevent deadlocks
spec_ref: specs/graph/bulk-loading.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## What

Sort labels into canonical (alphabetical) order before acquiring advisory locks in `AgeBulkLoadingStrategy`, preventing deadlocks when concurrent batches target overlapping label sets.

## Spec gap

**Concurrency Safety — Deterministic lock ordering:**
> - GIVEN a bulk loading operation that acquires locks on multiple labels
> - WHEN advisory locks are acquired
> - THEN labels MUST be sorted into a canonical order (e.g., alphabetical) before acquisition
> - AND locks are acquired strictly in that order to prevent deadlocks
> - AND if any lock acquisition fails, all previously acquired locks are released before retry

## Current state

`AgeBulkLoadingStrategy.apply_batch()` in `graph/infrastructure/age_bulk_loading/strategy.py`:

```python
all_labels = {op.label for op in create_nodes if op.label} | {
    op.label for op in create_edges if op.label
}
for label in all_labels:  # ← iterates over a Python set (non-deterministic order)
    self._queries.acquire_advisory_lock(cursor, graph_name, label)
```

Python sets have non-deterministic iteration order. Two concurrent batches targeting labels `["person", "repo"]` may acquire locks in opposite orders, creating a deadlock potential.

## Required changes

1. Change `for label in all_labels:` to `for label in sorted(all_labels):`.
2. Write a unit test confirming that given a set of labels `{"zebra", "alpha", "monkey"}`, locks are acquired in alphabetical order.
3. Verify the existing concurrency integration tests still pass.

## Notes

This is a small targeted fix — the rest of the bulk loading spec is implemented correctly.
