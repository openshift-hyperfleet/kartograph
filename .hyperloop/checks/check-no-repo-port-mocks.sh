#!/usr/bin/env bash
# check-no-repo-port-mocks.sh
#
# Detects AsyncMock()/MagicMock()/create_autospec() used for repository ports,
# authorization providers, and probe protocols in application-layer service test files.
#
# WHY THIS MATTERS
# ----------------
# The testing NFR requires that infrastructure ports (IKnowledgeGraphRepository,
# IDataSourceRepository, ISecretStoreRepository, AuthorizationProvider, etc.) and
# probe protocols be tested with in-memory fake implementations — NOT with
# AsyncMock(), MagicMock(), or create_autospec(). Mocking these ports:
#   - Hides real interface contract violations (a mock accepts any method call).
#   - Means changes to the port interface won't surface as test failures.
#   - For probes: MagicMock() silently swallows call arguments; a concrete
#     recording class makes missed or mis-parameterized probe calls visible.
#   - For repositories: AsyncMock() always returns the configured value regardless
#     of what was actually stored — state-based assertions are impossible.
#   - create_autospec() is equally prohibited: spec= does not make a mock a real
#     implementation — it still silently accepts any configured return value without
#     exercising the real protocol contract.
#
# Root cause this check addresses:
#   task-035: test_knowledge_graph_service.py defined @pytest.fixture functions
#   named mock_kg_repo, mock_ds_repo, mock_authz, mock_probe that returned
#   AsyncMock()/MagicMock() — all prohibited by the testing NFR.
#   InMemoryAuthorizationProvider already existed in tests/fakes/authorization.py
#   but was not used.
#
#   task-089: test_application_services.py (at tests/unit/query/ and tests/unit/graph/)
#   used create_autospec(IQueryGraphRepository, instance=True) and
#   create_autospec(QueryServiceProbe, instance=True) — same prohibition, different syntax.
#   These files were also placed outside the application/ subdirectory and therefore
#   escaped the previous path pattern.
#
# THREE FORMS DETECTED
# --------------------
# 1. Inline assignment form (inside a test method or fixture body):
#      mock_kg_repo = AsyncMock()
#      mock_kg_repo = create_autospec(IKnowledgeGraphRepository, instance=True)
#
# 2. Pytest fixture function form:
#      @pytest.fixture
#      def mock_kg_repo():
#          return AsyncMock()
#
# 3. create_autospec() called on a known port/probe type:
#      create_autospec(IXxxRepository, instance=True)
#      create_autospec(XxxServiceProbe, instance=True)
#
# VARIABLE/FUNCTION NAME PATTERNS CAUGHT
# ---------------------------------------
#   mock_*_repo     — IXxxRepository port
#   mock_*_store    — IXxxStore / IXxxStoreRepository port
#   mock_*_repository — IXxxRepository port (long-form)
#   mock_authz*     — AuthorizationProvider (InMemoryAuthorizationProvider exists)
#   mock_*probe*    — Probe protocol
#   probe*          — Probe protocol (short-form)
#
# TYPE PATTERNS CAUGHT (for create_autospec)
# ------------------------------------------
#   I[A-Z]\w*Repository — any repository port interface
#   I[A-Z]\w*Store      — any store port interface
#   \w+ServiceProbe     — any service probe protocol
#   \w+Probe            — any probe protocol
#   AuthorizationProvider
#
# CORRECT PATTERN
# ---------------
#   For repository ports — create an in-memory class implementing the port:
#     class InMemoryKnowledgeGraphRepository(IKnowledgeGraphRepository):
#         def __init__(self): self._store: dict = {}
#         async def save(self, kg): self._store[str(kg.id)] = kg
#         async def get_by_id(self, id_): return self._store.get(str(id_))
#
#   For AuthorizationProvider — use the existing fake:
#     from tests.fakes.authorization import InMemoryAuthorizationProvider
#
#   For probe protocols — create a concrete recording class:
#     class RecordingKnowledgeGraphServiceProbe(KnowledgeGraphServiceProbe):
#         def __init__(self): self.events: list = []
#         def knowledge_graph_created(self, **kw): self.events.append(kw)
#
# SCOPE
# -----
# Scans TWO sets of application-layer unit test files:
#   1. tests/unit/*/application/test_*.py  (standard location)
#   2. tests/unit/*/test_application_services.py  (flat location used by graph/query)
# Route tests and infrastructure tests are excluded — mocking services at the
# route layer is expected and acceptable.
#
# Usage:
#   ./check-no-repo-port-mocks.sh [test_dir]
#
# Exit 0 — no repository port or probe protocol mocks found (PASS)
# Exit 1 — one or more violations found (FAIL)

set -euo pipefail

TEST_DIR="${1:-src/api/tests}"

echo "=== Scanning for AsyncMock/MagicMock/create_autospec on repository ports and probe protocols ==="
echo "    Test dir: $TEST_DIR"
echo "    Scope   : tests/unit/*/application/test_*.py"
echo "              tests/unit/*/test_application_services.py"
echo ""

failures=0

# Build application-layer test file list.
# We look in TWO locations to avoid flagging route/infra tests:
#   1. tests/unit/*/application/test_*.py  — standard DDD-aligned location
#   2. tests/unit/*/test_application_services.py — flat location (graph, query contexts)
app_test_files=()
while IFS= read -r -d '' f; do
  app_test_files+=("$f")
done < <(find "$TEST_DIR/unit" \
    \( -path "*/application/test_*.py" \
       -o -name "test_application_services.py" \) \
    -not -path "*/.venv/*" \
    -not -path "*/__pycache__/*" \
    -print0 2>/dev/null || true)

if [[ ${#app_test_files[@]} -eq 0 ]]; then
  echo "  No application-layer test files found under $TEST_DIR/unit/*/application/."
  echo "  Nothing to scan."
  echo ""
  echo "PASS: No violations found (no application-layer test files to scan)."
  exit 0
fi

echo "  Scanning ${#app_test_files[@]} application-layer test file(s)."
echo ""

# ----------------------------------------------------------------------------
# FORM 1: Inline assignment — `mock_kg_repo = AsyncMock()`
# Uses PCRE (-P) to support \w and literal \( in pattern.
# ----------------------------------------------------------------------------
ASSIGNMENT_PATTERNS=(
  '\bmock_\w*_repo\s*=\s*(AsyncMock|MagicMock)\(\)'
  '\bmock_\w*_store\s*=\s*(AsyncMock|MagicMock)\(\)'
  '\bmock_\w*_repository\s*=\s*(AsyncMock|MagicMock)\(\)'
  '\bmock_authz\w*\s*=\s*(AsyncMock|MagicMock)\(\)'
  '\bmock_\w*probe\w*\s*=\s*(AsyncMock|MagicMock)\(\)'
  '\bprobe\w*\s*=\s*(AsyncMock|MagicMock)\(\)'
)

# ----------------------------------------------------------------------------
# FORM 3: create_autospec() on repository port or probe type
#
# Catches patterns like:
#   create_autospec(IQueryGraphRepository, instance=True)
#   create_autospec(QueryServiceProbe, instance=True)
#   return create_autospec(IXxxRepository, instance=True)
#
# TYPE_PATTERNS match the first argument of create_autospec():
#   I[A-Z]\w*Repository  — any IXxx repository interface
#   I[A-Z]\w*Store       — any IXxx store interface
#   \w+Probe             — any Probe protocol (XxxServiceProbe, XxxProbe)
#   AuthorizationProvider
# ----------------------------------------------------------------------------
AUTOSPEC_TYPE_PATTERNS=(
  'create_autospec\(\s*I[A-Z]\w*Repository'
  'create_autospec\(\s*I[A-Z]\w*Store'
  'create_autospec\(\s*\w+Probe'
  'create_autospec\(\s*AuthorizationProvider'
)

# ----------------------------------------------------------------------------
# FORM 2: Pytest fixture function — `def mock_kg_repo(): return AsyncMock()`
#
# Strategy: for each fixture name pattern, grep for matching function defs,
# then inspect the next 5 lines for a bare `return AsyncMock()/MagicMock()`.
# Uses PCRE (-P) to support \w metacharacter.
#
# Fixture NAME patterns (what comes after `def `):
# ----------------------------------------------------------------------------
FIXTURE_NAME_PATTERNS=(
  'mock_\w*_repo'
  'mock_\w*_store'
  'mock_\w*_repository'
  'mock_authz\w*'
  'mock_\w*probe\w*'
  'probe\w*'
)

scan_fixture_form() {
  local test_file="$1"
  local result=""

  for name_pat in "${FIXTURE_NAME_PATTERNS[@]}"; do
    # Match lines like `def mock_kg_repo():` using PCRE.
    # The pattern anchors on `def ` prefix and requires a `(` after the name.
    local def_hits
    def_hits=$(grep -Pn "def ${name_pat}\s*\(" "$test_file" 2>/dev/null || true)
    [[ -z "$def_hits" ]] && continue

    while IFS= read -r def_line; do
      lineno=$(echo "$def_line" | cut -d: -f1)
      [[ -z "$lineno" ]] && continue

      # Read the next 5 lines after the function def.
      end_line=$(( lineno + 5 ))
      body=$(sed -n "${lineno},${end_line}p" "$test_file" 2>/dev/null || true)

      # Look for a bare `return AsyncMock()`/`return MagicMock()`/`return create_autospec()`.
      if echo "$body" | grep -qE "return (AsyncMock|MagicMock)\(\)|return create_autospec\("; then
        func_name=$(echo "$def_line" | grep -oP 'def \w+' | head -1)
        return_line=$(echo "$body" | grep -nE "return (AsyncMock|MagicMock)\(\)|return create_autospec\(" | head -1)
        result="${result}    (fixture) line ${lineno}: ${func_name}() → ${return_line}"$'\n'
      fi
    done <<< "$def_hits"
  done

  echo "$result"
}

for test_file in "${app_test_files[@]}"; do
  file_flagged=0
  file_hits=""

  # --- Form 1: inline assignment patterns (AsyncMock/MagicMock) ---
  for pattern in "${ASSIGNMENT_PATTERNS[@]}"; do
    hits=$(grep -Pn "$pattern" "$test_file" 2>/dev/null || true)
    if [[ -n "$hits" ]]; then
      while IFS= read -r hit; do
        file_hits="${file_hits}    (assignment) ${hit}"$'\n'
      done <<< "$hits"
      file_flagged=1
    fi
  done

  # --- Form 2: pytest fixture function returning AsyncMock/MagicMock/create_autospec ---
  fixture_hits=$(scan_fixture_form "$test_file")
  if [[ -n "$fixture_hits" ]]; then
    file_hits="${file_hits}${fixture_hits}"
    file_flagged=1
  fi

  # --- Form 3: create_autospec() on repository port or probe type ---
  for pattern in "${AUTOSPEC_TYPE_PATTERNS[@]}"; do
    hits=$(grep -Pn "$pattern" "$test_file" 2>/dev/null || true)
    if [[ -n "$hits" ]]; then
      while IFS= read -r hit; do
        file_hits="${file_hits}    (create_autospec) ${hit}"$'\n'
      done <<< "$hits"
      file_flagged=1
    fi
  done

  if [[ $file_flagged -eq 1 ]]; then
    echo "  [FAIL] Repository port or probe mocked in: $test_file"
    echo "$file_hits"
    failures=$((failures + 1))
    echo "  FIX: Replace AsyncMock()/MagicMock()/create_autospec() with in-memory fake implementations:"
    echo "    1. For repository ports (mock_*_repo, mock_*_store):"
    echo "       Create an in-memory class implementing the port interface:"
    echo "         class InMemoryKnowledgeGraphRepository(IKnowledgeGraphRepository):"
    echo "             def __init__(self): self._store: dict = {}"
    echo "             async def save(self, kg): self._store[str(kg.id)] = kg"
    echo "             async def get_by_id(self, id_): return self._store.get(str(id_))"
    echo "    2. For AuthorizationProvider (mock_authz):"
    echo "       Import and use InMemoryAuthorizationProvider from tests/fakes/authorization.py."
    echo "    3. For probe protocols (mock_probe, mock_*_probe):"
    echo "       Create a concrete recording class implementing the protocol:"
    echo "         class RecordingKnowledgeGraphServiceProbe(KnowledgeGraphServiceProbe):"
    echo "             def __init__(self): self.events: list = []"
    echo "             def knowledge_graph_created(self, **kw): self.events.append(kw)"
    echo ""
  fi
done

echo "=== Summary ==="
echo "  Files with repository port / probe protocol mock violations: $failures"
echo ""

if [[ $failures -gt 0 ]]; then
  echo "FAIL: $failures file(s) contain AsyncMock()/MagicMock()/create_autospec() for"
  echo "      repository ports or probe protocols in application-layer tests."
  echo "      The testing NFR requires in-memory fake implementations, not mocks."
  echo "      create_autospec() is equally prohibited — spec= does not make a real implementation."
  echo "      See FIX instructions above for the correct pattern."
  exit 1
else
  echo "PASS: No repository port or probe protocol mocks found in application-layer tests."
  exit 0
fi
