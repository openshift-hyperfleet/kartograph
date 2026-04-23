---
id: task-028
title: Fix /health/db to return HTTP 503 when database is unreachable
spec_ref: specs/nfr/health-checks.spec.md@b46589a2419c1bf08c2dd08c311ee95642139703
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## What

The `GET /health/db` endpoint currently returns HTTP 200 with `{"status": "error"}` in
the response body when the database is unreachable. The spec requires it to return
**HTTP 503 Service Unavailable**.

This matters because Kubernetes readiness probes inspect HTTP status codes, not response
bodies. A 200 with an error body will cause Kubernetes to consider the pod ready even
when the database is down.

## Spec Scenarios Addressed

**Requirement: Database Health Check**

- Scenario: Database is unreachable → `GET /health/db` returns **503** with an error
  message in the body (currently returns 200 — this is the bug)
- Scenario: Database is reachable → `GET /health/db` returns 200 (currently correct,
  must remain correct)

## Where the Bug Is

`src/api/main.py` — the `health_db()` function:

```python
@app.get("/health/db")
def health_db(client: Annotated[AgeGraphClient, Depends(get_age_graph_client)]) -> dict:
    try:
        is_healthy = client.verify_connection()
        return {"status": "ok" if is_healthy else "unhealthy", ...}
    except Exception as e:
        # BUG: returns 200 with error body instead of 503
        return {"status": "error", "connected": False, "error": str(e)}
```

## Work Required

1. **Write tests first** (TDD). Add to `src/api/tests/test_health.py`:
   - `test_health_db_returns_503_when_database_unreachable`: mock `AgeGraphClient` to
     raise an exception; assert response status code is 503.
   - `test_health_db_returns_200_when_healthy`: mock `AgeGraphClient.verify_connection()`
     to return True; assert response status code is 200.
   - `test_health_db_returns_503_when_verify_returns_false`: mock
     `verify_connection()` to return False; assert response status code is 503.

2. **Fix the implementation** in `src/api/main.py`. Inject `Response` to set the status
   code:
   ```python
   from fastapi import Response

   @app.get("/health/db")
   def health_db(
       response: Response,
       client: Annotated[AgeGraphClient, Depends(get_age_graph_client)],
   ) -> dict:
       try:
           is_healthy = client.verify_connection()
           if not is_healthy:
               response.status_code = 503
               return {"status": "unhealthy", "connected": client.is_connected(), ...}
           return {"status": "ok", "connected": True, "graph_name": client.graph_name}
       except Exception as e:
           response.status_code = 503
           return {"status": "error", "connected": False, "error": str(e)}
   ```

## Acceptance Criteria

- `GET /health/db` returns HTTP 503 when the database is unreachable or unhealthy
- `GET /health/db` returns HTTP 200 when the database is reachable and healthy
- Unit tests cover both code paths (exception raised, verify_connection returns False/True)
- All existing tests continue to pass
