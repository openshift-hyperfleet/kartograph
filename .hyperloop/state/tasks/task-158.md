---
id: task-158
title: 'Fix query catch-all error type: ''unexpected_error'' → ''unknown_error'''
spec_ref: specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2
status: in_progress
phase: verify
deps: []
round: 1
branch: hyperloop/task-158
pr: https://github.com/openshift-hyperfleet/kartograph/pull/629
pr_title: 'fix(query): rename unexpected_error to unknown_error per spec'
pr_description: "## What and Why\n\n`query-execution.spec.md` — Requirement: Error\
  \ Categorization — specifies\nthat the error type for unexpected (catch-all) failures\
  \ SHALL be\n`\"unknown_error\"`. However, `MCPQueryService.execute_cypher_query()`\
  \ currently\nemits `error_type=\"unexpected_error\"` in its bare `except Exception`\
  \ handler.\nAll unit tests were written against the wrong string and therefore pass\
  \ today\nwhile masking the spec violation.\n\nThis PR brings code and tests into\
  \ alignment with the spec.\n\n## Spec Requirements Satisfied\n\n`specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2`\n\
  \n### Requirement: Error Categorization\n> **Scenario: Unexpected error**\n> - GIVEN\
  \ an unexpected failure during query execution\n> - THEN the error type is `\"unknown_error\"\
  `\n\n## Key Design Decision\n\n`\"unknown_error\"` is the spec-mandated label because\
  \ it signals to the\nconsumer that the server itself does not know what category\
  \ of error occurred —\nwhich is semantically more honest than `\"unexpected_error\"\
  ` (which implies the\nserver knows the error was unexpected but chose that label).\
  \ The string also\naligns with well-established error vocabularies (e.g., gRPC's\
  \ `UNKNOWN` status).\n\nNo other error type values are affected:\n- `\"forbidden\"\
  ` — keyword blacklist rejection (unchanged)\n- `\"timeout\"` — statement timeout\
  \ (unchanged)\n- `\"execution_error\"` — syntax / runtime failure (unchanged)\n\
  - `\"unknown_error\"` — catch-all (this fix)\n\n## Files / Areas Affected\n\n###\
  \ Production code (1 line change)\n- `src/api/query/application/services.py`\n \
  \ — In the bare `except Exception` handler of `execute_cypher_query()`,\n    change\
  \ `error_type=\"unexpected_error\"` → `error_type=\"unknown_error\"`.\n\n### Unit\
  \ tests (string literal updates only, logic unchanged)\n- `src/api/tests/unit/query/test_mcp_query_service.py`\n\
  \  — Four assertions in `TestErrorCategorization`:\n    `test_unexpected_error_type_when_repo_raises_unexpected_exception`,\n\
  \    `test_unexpected_error_for_value_error`,\n    `test_unexpected_error_for_type_error`,\n\
  \    `test_unexpected_error_has_no_correlation_id`\n    — change `\"unexpected_error\"\
  ` → `\"unknown_error\"`.\n- `src/api/tests/unit/query/test_application_services.py`\n\
  \  — `test_categorizes_unexpected_error` assertion.\n- `src/api/tests/unit/query/test_mcp_query_tool.py`\n\
  \  — Tests in `TestBuildErrorResponseUnexpectedErrors` that construct\n    `QueryError(error_type=\"\
  unexpected_error\", ...)` and assert\n    `result[\"error_type\"] == \"unexpected_error\"\
  `.\n  — `test_all_errors_have_success_false`: update the `\"unexpected_error\"`\n\
  \    entry in the iteration tuple to `\"unknown_error\"`.\n\n## How to Verify\n\n\
  ```bash\ncd src/api\nuv run pytest tests/unit/query/ -v\n```\n\nAll tests must pass.\
  \ Pay particular attention to:\n- `TestErrorCategorization` in `test_mcp_query_service.py`\n\
  - `TestBuildErrorResponseUnexpectedErrors` in `test_mcp_query_tool.py`\n- `test_categorizes_unexpected_error`\
  \ in `test_application_services.py`\n\nWith the dev instance running, also verify\
  \ the integration path:\n```bash\nuv run pytest tests/integration/test_query_mcp.py\
  \ -v -m integration\n```\n\n## Caveats\n\n- The `_build_error_response` helper in\
  \ `query/presentation/mcp.py` passes\n  `error_type` through verbatim; no change\
  \ is needed there.\n- No UI code references `\"unexpected_error\"` or `\"unknown_error\"\
  ` by string,\n  so no frontend changes are required.\n- Any external MCP clients\
  \ that pattern-match on `\"unexpected_error\"` will\n  need to update their handling.\
  \ No such clients are tracked in this repo."
---
