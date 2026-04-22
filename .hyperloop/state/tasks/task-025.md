---
id: task-025
title: Add missing JWT authentication test — invalid Bearer with valid API key returns 401 immediately
spec_ref: specs/shared-kernel/jwt-authentication.spec.md@224a54b5ab2f7bca552b3845891a363215b7110b
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## What

The Authentication Priority requirement in `specs/shared-kernel/jwt-authentication.spec.md` has three scenarios. Two are covered by tests in `test_authenticate_dependency.py`, but this scenario is missing:

> **Scenario: Invalid Bearer token with API key present**
> - GIVEN a request with an invalid Bearer token and a valid API key
> - WHEN the request is authenticated
> - THEN authentication fails immediately (Bearer is not silently skipped)

The code in `iam/dependencies/user.py` (`_authenticate()`) correctly implements this — if a Bearer token is present but invalid, it raises `HTTPException(401)` immediately without attempting API key authentication. However, no test exercises this specific condition (invalid JWT + valid API key both provided simultaneously).

The existing test `test_raises_401_for_invalid_jwt` only tests an invalid JWT without a concurrent API key header present.

## How

Add a unit test in `src/api/tests/unit/iam/dependencies/test_authenticate_dependency.py` that:

1. Provides a request with an invalid Bearer token header
2. Also provides a valid `X-API-Key` header
3. Asserts the response is `401` (not the API key's user)
4. Asserts the API key service was not consulted (the Bearer failure is not silently skipped)

## Acceptance

- New unit test added to `test_authenticate_dependency.py`
- Test does not use `MagicMock` for domain/application collaborators (use fakes)
- Test confirms that a valid API key does NOT rescue an invalid Bearer token
- No production code changes needed
