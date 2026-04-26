#!/usr/bin/env bash
# check-pytest-env-skip-if-set.sh
#
# Verifies that every network-location variable in [tool.pytest_env]
# (names containing ENDPOINT, PORT, HOST, URL, URI, ADDR, or ADDRESS)
# uses the dict form `{ value = "...", skip_if_set = true }` rather than
# a bare string literal.
#
# WHY: `make instance-up` assigns unique ports per isolated instance and
# exports them as environment variables before pytest runs.  A bare string
# assignment in [tool.pytest_env] is applied AFTER the environment — it
# overrides those variables, so all SpiceDB / database integration tests
# silently connect to wrong ports and fail with SSL or connection errors.
# The dict form with `skip_if_set = true` preserves whatever the instance
# manager already set.
#
# EXAMPLE FAIL (bare string — overrides isolated-instance port):
#   SPICEDB_ENDPOINT = "localhost:50051"
#
# EXAMPLE PASS (dict with skip_if_set — honours instance manager):
#   SPICEDB_ENDPOINT = { value = "localhost:50051", skip_if_set = true }
#
# Usage:
#   bash .hyperloop/checks/check-pytest-env-skip-if-set.sh
#
# Exit 0  — all network-location vars use skip_if_set = true (or none exist).
# Exit 1  — one or more network-location vars are bare string literals.

set -uo pipefail

PYPROJECT="$(git rev-parse --show-toplevel)/src/api/pyproject.toml"

if [[ ! -f "$PYPROJECT" ]]; then
  echo "INFO: $PYPROJECT not found — nothing to check."
  exit 0
fi

VIOLATIONS=()
in_section=0

while IFS= read -r line; do
  # Detect [tool.pytest_env] section start
  if [[ "$line" =~ ^\[tool\.pytest_env\] ]]; then
    in_section=1
    continue
  fi

  # Any other section header exits the pytest_env block
  if [[ "$in_section" -eq 1 && "$line" =~ ^\[ ]]; then
    in_section=0
  fi

  [[ "$in_section" -eq 0 ]] && continue

  # Skip blank lines and comment lines
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

  # A bare string assignment looks like:  VARNAME = "..."
  # A dict assignment looks like:         VARNAME = { value = "...", ... }
  # We only care about variables whose names contain a network-location keyword.
  #
  # The regex matches lines of the form:
  #   <optional prefix><KEYWORD><optional suffix> = "<value>"
  # (The `= "` at the end distinguishes bare strings from dict forms.)
  if echo "$line" | grep -qE \
    '^[A-Z0-9_]*(ENDPOINT|PORT|HOST|URL|URI|ADDR|ADDRESS)[A-Z0-9_]* *= *"'; then
    VIOLATIONS+=("  $line")
  fi
done < "$PYPROJECT"

if [[ ${#VIOLATIONS[@]} -eq 0 ]]; then
  echo "PASS: All network-location pytest_env vars use skip_if_set = true."
  exit 0
fi

echo "FAIL: The following network-location variables in [tool.pytest_env] of"
echo "      src/api/pyproject.toml are bare string literals.  They override"
echo "      isolated-instance environment variables set by \`make instance-up\`,"
echo "      causing integration tests to connect to wrong ports."
echo ""
for v in "${VIOLATIONS[@]}"; do
  echo "$v"
done
echo ""
echo "Fix: replace each bare assignment with the skip_if_set dict form, e.g.:"
echo "  SPICEDB_ENDPOINT = { value = \"localhost:50051\", skip_if_set = true }"
echo ""
exit 1
