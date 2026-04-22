---
id: task-026
title: Add SpiceDB client unit tests for all behavioral scenarios
spec_ref: specs/shared-kernel/spicedb-authorization.spec.md@224a54b5ab2f7bca552b3845891a363215b7110b
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## What

`specs/shared-kernel/spicedb-authorization.spec.md` defines behavioral scenarios for the SpiceDB authorization provider. The existing `test_client.py` only tests input validation and protobuf-building helpers. The behavioral scenarios are covered by integration tests but have **no unit-level coverage**. Critically, `bulk_check_permission` has **no tests at any level**.

### Gaps by requirement

**Bulk Permission Checking** — *no tests exist at any level*
- Scenario: Filter accessible resources — `bulk_check_permission([...], permission)` returns only resource IDs the user has permission on

**Permission Checking** — only integration tests exist
- Scenario: Permission granted — `check_permission(...)` returns `True`
- Scenario: Permission denied — `check_permission(...)` returns `False`
- Scenario: Computed permission via inheritance — permission returns `True` when derived through group chain

**Relationship Writes** — only integration tests exist
- Scenario: Single relationship — `write_relationship(...)` creates relationship; future checks reflect it
- Scenario: Bulk relationships — `write_relationships([...])` creates all atomically

**Relationship Deletion** — validation tested; behavior only in integration tests
- Scenario: Single deletion — `delete_relationship(...)` removes it; future checks exclude it
- Scenario: Filter-based deletion — `delete_relationships_by_filter(...)` removes all matching

**Resource Lookup** — only integration tests exist
- Scenario: Lookup accessible workspaces — `lookup_resources(...)` returns correct resource IDs

**Relationship Reading** — validation tested; behavior only in integration tests
- Scenario: Read explicit tuples — `read_relationships(...)` returns only directly-written tuples, not computed permissions

## How

Add unit tests in `src/api/tests/unit/shared_kernel/authorization/test_client.py` using mocked gRPC channels (acceptable per the testing NFR: "mocking is acceptable ONLY for: HTTP clients, gRPC channels, filesystem I/O, or clock/time"):

1. Mock `authzed.api.v1.PermissionsServiceStub` to control gRPC responses
2. Write a test class per requirement group
3. For `bulk_check_permission`: test the filtering behavior with a mix of permitted/denied resources
4. For behavioral scenarios: assert the correct gRPC method is called with correct arguments and the result is mapped correctly

## Acceptance

- All 7 requirements from the spec have at least one unit test per scenario
- `bulk_check_permission` gains at least one test (currently has zero at any level)
- Tests use mocked gRPC stubs (not MagicMock on domain collaborators)
- No production code changes needed (unless `bulk_check_permission` has a behavioral bug uncovered by the tests)
