# Spec Alignment Reviewer Memory

## Learnings

### 2026-04-22 | API Keys spec review | PASS | task-021

**Pattern:** IAM bounded context follows DDD layers consistently: domain aggregate -> application service -> infrastructure repository -> presentation routes. All layers have corresponding unit tests.

**Pattern:** Cascade deletion is implemented at the application service layer (TenantService.delete_tenant), not via DB cascades. The DB FK uses RESTRICT to enforce application-layer handling. Integration tests for cascade are in `test_tenant_service.py`.

**Pattern:** Authorization (SpiceDB) integration tests live in `tests/integration/test_api_key_auth.py` with `pytest.mark.keycloak` marker. These require a running instance and are not run in unit test pass.

**Pattern:** Prefix collision probe uses `logger.error()` at the infrastructure layer (`DefaultAPIKeyRepositoryProbe.api_key_prefix_collision`). The spec requires "error-level event" — verify this is `error()` not `warning()`.

**Pattern:** JWT-first precedence is implemented in `iam/dependencies/user.py::_authenticate()` as an if/elif chain: JWT checked first via `token is not None`, then API key via `x_api_key is not None`. Integration test `test_invalid_jwt_with_valid_api_key_uses_api_key` validates JWT-error-takes-precedence behavior (not fallthrough).

**Action:** When reviewing "plaintext returned once" scenarios, check: (1) the response model does NOT include the secret field in non-creation endpoints, and (2) the plaintext is only returned from the creation service call tuple.

**Action:** For cascade deletion spec, check both the aggregate's `mark_for_deletion()` event emission (for auth cleanup) AND the repository's `delete()` method. Both are required.
