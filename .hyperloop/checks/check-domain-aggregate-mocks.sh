#!/usr/bin/env bash
# check-domain-aggregate-mocks.sh
#
# Detects MagicMock()/AsyncMock() (without spec=) used for domain aggregates
# in service-layer and application-layer test files.
#
# WHY THIS MATTERS
# ----------------
# Domain aggregates (DataSource, KnowledgeGraph, SyncRun, ApiKey, etc.) carry
# domain validation logic. Mocking them with MagicMock() means:
#   - No domain invariants are exercised.
#   - New constraints added to the aggregate won't be caught by these tests.
#   - Attribute access always succeeds — a mocked DataSource has no real fields.
#
# The correct pattern is to instantiate real domain objects, typically via a
# factory helper (e.g., _make_ds(), _make_kg()) defined in the same or a
# sibling test file. If no factory exists, create one.
#
# PATTERNS CAUGHT (in service/application test files)
# ---------------------------------------------------
# Variable names that match domain aggregate patterns, assigned MagicMock():
#   ds1 = MagicMock()           # DataSource aggregate — use _make_ds()
#   ds_with_creds = MagicMock() # DataSource aggregate — use real DataSource
#   kg = MagicMock()            # KnowledgeGraph aggregate — use _make_kg()
#   knowledge_graph = MagicMock()
#   sync_run = MagicMock()
#   api_key = MagicMock()
#
# PATTERNS ALLOWED (infrastructure/observability — not flagged)
# -------------------------------------------------------------
#   session = MagicMock()       # DB session (infrastructure)
#   mock_probe = MagicMock()    # domain probe (observability)
#   client = MagicMock()        # HTTP client (infrastructure)
#
# SCOPE
# -----
# Scans test files under tests/unit in the management, identity, ingestion,
# extraction, graph, and querying bounded contexts.
# Files in .venv/ and __pycache__/ are always excluded.
#
# Usage:
#   ./check-domain-aggregate-mocks.sh [test_dir]
#
# Exit 0 — no domain aggregate mocks found (PASS)
# Exit 1 — one or more domain aggregate mocks found (FAIL)

set -euo pipefail

TEST_DIR="${1:-src/api/tests}"

echo "=== Scanning for bare MagicMock/AsyncMock on domain aggregates ==="
echo "    Test dir: $TEST_DIR"
echo ""

failures=0

# Domain aggregate variable name patterns — matches common short names and
# descriptive variants used across all bounded contexts.
#
# The regex anchors on word boundary before the variable name so that
# mock_service, mock_probe, mock_session, etc. are NOT matched.
#
# Captured bounded-context aggregates:
#   Management : DataSource (ds*), KnowledgeGraph (kg*, knowledge_graph*)
#   Identity   : ApiKey (api_key*, apikey*)
#   Extraction : SyncRun (sync_run*)
#   Graph      : (extends above)
#   Ingestion  : JobPackage (job_package*, jobpackage*)

DOMAIN_PATTERNS=(
  # DataSource aggregate — ds, ds1, ds2, ds_with_creds, data_source, etc.
  '\bds\d*\s*=\s*(MagicMock|AsyncMock)\(\)'
  '\bds_\w+\s*=\s*(MagicMock|AsyncMock)\(\)'
  '\bdata_source\w*\s*=\s*(MagicMock|AsyncMock)\(\)'

  # KnowledgeGraph aggregate
  '\bkg\d*\s*=\s*(MagicMock|AsyncMock)\(\)'
  '\bkg_\w+\s*=\s*(MagicMock|AsyncMock)\(\)'
  '\bknowledge_graph\w*\s*=\s*(MagicMock|AsyncMock)\(\)'

  # ApiKey aggregate
  '\bapi_key\w*\s*=\s*(MagicMock|AsyncMock)\(\)'
  '\bapikey\w*\s*=\s*(MagicMock|AsyncMock)\(\)'

  # SyncRun aggregate
  '\bsync_run\w*\s*=\s*(MagicMock|AsyncMock)\(\)'
  '\bsyncrun\w*\s*=\s*(MagicMock|AsyncMock)\(\)'

  # JobPackage aggregate
  '\bjob_package\w*\s*=\s*(MagicMock|AsyncMock)\(\)'

  # User / Team / Tenant aggregates (Identity context)
  '\btenant\w*\s*=\s*(MagicMock|AsyncMock)\(\)'
)

# Exclusion patterns — lines that match these are infrastructure/observability
# and are allowed to use MagicMock() without spec=.
EXCLUSION_PATTERNS=(
  'session'
  'probe'
  'client'
  'conn'
  'cursor'
  'logger'
  'request'
  'response'
)

# Build service/application test file list
service_test_files=()
while IFS= read -r -d '' f; do
  service_test_files+=("$f")
done < <(find "$TEST_DIR" \
    -name "test_*.py" \
    -not -path "*/.venv/*" \
    -not -path "*/__pycache__/*" \
    -print0 2>/dev/null || true)

if [[ ${#service_test_files[@]} -eq 0 ]]; then
  echo "  No test files found under $TEST_DIR. Nothing to scan."
  echo ""
  echo "PASS: No domain aggregate mocks found (no test files)."
  exit 0
fi

echo "  Scanning ${#service_test_files[@]} test file(s) for domain aggregate mocks."
echo ""

for test_file in "${service_test_files[@]}"; do
  file_flagged=0

  for pattern in "${DOMAIN_PATTERNS[@]}"; do
    hits=$(grep -inP "$pattern" "$test_file" 2>/dev/null || true)

    if [[ -z "$hits" ]]; then
      continue
    fi

    # Filter out exclusion patterns (infrastructure/observability)
    filtered_hits="$hits"
    for excl in "${EXCLUSION_PATTERNS[@]}"; do
      filtered_hits=$(echo "$filtered_hits" | grep -iv "$excl" || true)
    done

    if [[ -n "$filtered_hits" ]]; then
      if [[ $file_flagged -eq 0 ]]; then
        echo "  [FAIL] Domain aggregate mocked in: $test_file"
        file_flagged=1
      fi
      echo "$filtered_hits" | sed 's/^/    /'
      failures=$((failures + 1))
    fi
  done

  if [[ $file_flagged -eq 1 ]]; then
    echo ""
    echo "  FIX: Replace MagicMock() with a real domain object:"
    echo "    1. Check for an existing _make_ds()/_make_kg() factory in a sibling"
    echo "       test file for the same bounded context and reuse it."
    echo "    2. If no factory exists, create one using the real domain constructor."
    echo "    3. Assign real attributes directly: obj.credentials_path = 'vault/...'."
    echo "    MagicMock(spec=DataSource) is also acceptable when the test only"
    echo "    needs the interface, not the validation logic."
    echo ""
  fi
done

echo "=== Summary ==="
echo "  Domain aggregate mock violations: $failures"
echo ""

if [[ $failures -gt 0 ]]; then
  echo "FAIL: $failures domain aggregate variable(s) assigned MagicMock() or AsyncMock()."
  echo "      Domain aggregates must be real instances (or spec-d mocks) so that"
  echo "      domain validation logic is exercised and interface regressions surface."
  exit 1
else
  echo "PASS: No bare MagicMock/AsyncMock on domain aggregate variables found."
  exit 0
fi
