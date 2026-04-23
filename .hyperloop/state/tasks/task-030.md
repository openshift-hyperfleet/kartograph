---
id: task-030
title: Add unit tests for CORS configuration and conditional middleware installation
spec_ref: specs/nfr/cors.spec.md@b46589a2419c1bf08c2dd08c311ee95642139703
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## What

The CORS implementation in `src/api/main.py` and `src/api/infrastructure/settings.py`
is correct, but there are **no unit tests** verifying the conditional CORS behavior.
Without tests, a refactor could silently break the conditional installation or default
policy.

## Spec Scenarios Addressed

**Requirement: Configurable CORS Origins**
- Scenario: Origins configured → CORS middleware is installed with those origins
- Scenario: No origins configured → CORS middleware is NOT installed

**Requirement: CORS Defaults**
- Scenario: Default policy → all HTTP methods and all request headers allowed when
  CORS is enabled

## Where the Gaps Are

No test file exists for CORS behavior. The two testable units are:

1. **`CORSSettings`** in `src/api/infrastructure/settings.py`:
   - `is_enabled` returns `False` when `origins` is empty
   - `is_enabled` returns `True` when `origins` has one or more entries
   - Default `allow_credentials` is `True`
   - Default `allow_methods` includes all standard HTTP verbs
   - Default `allow_headers` is `["*"]`

2. **Conditional middleware installation** in `main.py`:
   - `CORSMiddleware` is added to the app when `cors_settings.is_enabled` is `True`
   - `CORSMiddleware` is NOT added when `cors_settings.is_enabled` is `False`
   - When installed, `allow_credentials=True` and explicit `allow_origins` list (not `["*"]`)

## Work Required

Create `src/api/tests/unit/infrastructure/test_cors_settings.py`:

```python
from infrastructure.settings import CORSSettings

class TestCORSSettingsIsEnabled:
    def test_disabled_by_default(self):
        settings = CORSSettings()
        assert settings.is_enabled is False

    def test_enabled_when_origins_configured(self):
        settings = CORSSettings(origins=["https://example.com"])
        assert settings.is_enabled is True

    def test_disabled_when_origins_empty_list(self):
        settings = CORSSettings(origins=[])
        assert settings.is_enabled is False

class TestCORSSettingsDefaults:
    def test_credentials_allowed_by_default(self):
        settings = CORSSettings(origins=["https://example.com"])
        assert settings.allow_credentials is True

    def test_all_methods_allowed_by_default(self):
        settings = CORSSettings(origins=["https://example.com"])
        for method in ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]:
            assert method in settings.allow_methods

    def test_all_headers_allowed_by_default(self):
        settings = CORSSettings(origins=["https://example.com"])
        assert "*" in settings.allow_headers

    def test_wildcard_not_used_as_origin_when_credentials_enabled(self):
        # Spec: wildcard MUST NOT be used when credentials are allowed
        settings = CORSSettings(origins=["https://example.com"])
        assert "*" not in settings.origins
```

Add CORS middleware installation tests in `src/api/tests/unit/test_app_cors.py` using
FastAPI's `TestClient` with mocked `get_cors_settings()`:

```python
def test_cors_middleware_not_installed_when_no_origins():
    # Override settings to return empty origins
    # Make a cross-origin request and assert no CORS headers returned

def test_cors_middleware_installed_when_origins_configured():
    # Override settings to return ["https://example.com"]
    # Make a cross-origin request from that origin and assert CORS headers present
```

## Acceptance Criteria

- `CORSSettings.is_enabled` is tested for empty and non-empty origins
- Default policy (credentials, methods, headers) is verified by unit tests
- Conditional middleware installation is tested (at minimum: disabled case)
- No production code changes needed (implementation is correct)
- All new tests pass with `make test-unit`
