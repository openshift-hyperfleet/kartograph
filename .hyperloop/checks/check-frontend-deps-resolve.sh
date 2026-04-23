#!/usr/bin/env bash
# check-frontend-deps-resolve.sh
#
# Verifies that every package listed in src/dev-ui/package.json
# devDependencies and dependencies actually appears resolved in
# pnpm-lock.yaml. A package that is declared but absent from the
# lockfile means `pnpm install` failed (e.g. non-existent version
# constraint such as vitest@^2.2.5 when 2.x topped at 2.1.9).
#
# This check catches the gap in check-frontend-test-infrastructure.sh,
# which only verifies that the string "vitest" appears in package.json —
# not that the version resolved successfully.
#
# Usage:
#   ./check-frontend-deps-resolve.sh [ui_dir]
#
# Exit 0  — no package.json, or all dependencies appear in pnpm-lock.yaml.
# Exit 1  — one or more packages are declared but absent from the lockfile.

set -euo pipefail

UI_DIR="${1:-src/dev-ui}"
PACKAGE_JSON="$UI_DIR/package.json"
LOCK_FILE="$UI_DIR/pnpm-lock.yaml"

if [[ ! -f "$PACKAGE_JSON" ]]; then
  echo "No $PACKAGE_JSON found. Skipping dependency resolution check."
  exit 0
fi

echo "=== Checking frontend dependency resolution in: $UI_DIR ==="

# Check lockfile exists — its absence means pnpm install was never run.
if [[ ! -f "$LOCK_FILE" ]]; then
  echo ""
  echo "FAIL: $LOCK_FILE does not exist."
  echo "Run 'cd $UI_DIR && pnpm install' to install and lock dependencies."
  echo "If pnpm install fails with ERR_PNPM_NO_MATCHING_VERSION, a declared"
  echo "package version does not exist in the registry — fix it before re-running."
  exit 1
fi

# Extract all declared package names from devDependencies and dependencies.
# Requires Python (available via uv in this repo).
if ! command -v python3 &>/dev/null && ! command -v uv &>/dev/null; then
  echo "WARN: python3 and uv not found; cannot parse package.json. Skipping deep check."
  echo "PASS: pnpm-lock.yaml exists (shallow check only)."
  exit 0
fi

if command -v uv &>/dev/null; then
  PY="uv run python"
else
  PY="python3"
fi

# Parse dependency names out of package.json.
dep_names=$($PY - "$PACKAGE_JSON" <<'EOF'
import json, sys
path = sys.argv[1]
with open(path) as f:
    pkg = json.load(f)
deps = {}
deps.update(pkg.get("dependencies", {}))
deps.update(pkg.get("devDependencies", {}))
for name in sorted(deps.keys()):
    print(name)
EOF
)

if [[ -z "$dep_names" ]]; then
  echo "PASS: No dependencies declared in $PACKAGE_JSON."
  exit 0
fi

failed=0

while IFS= read -r pkg_name; do
  [[ -z "$pkg_name" ]] && continue
  # The lockfile contains package names in quoted form, e.g.:
  #   vitest@^2.1.9:
  # or under the packages section as:
  #   'vitest@2.1.9':
  # A simple grep for the package name is sufficient to detect resolution.
  if ! grep -q "\"${pkg_name}\"" "$LOCK_FILE" 2>/dev/null && \
     ! grep -q "'${pkg_name}" "$LOCK_FILE" 2>/dev/null && \
     ! grep -q "${pkg_name}@" "$LOCK_FILE" 2>/dev/null; then
    echo "FAIL: '$pkg_name' is declared in $PACKAGE_JSON but not found in $LOCK_FILE."
    echo "  This means pnpm install failed to resolve this package."
    echo "  Verify the version constraint is valid: pnpm view ${pkg_name} versions --json"
    failed=$((failed + 1))
  fi
done <<< "$dep_names"

echo ""
if [[ $failed -gt 0 ]]; then
  echo "FAIL: $failed package(s) declared in $PACKAGE_JSON are missing from $LOCK_FILE."
  echo ""
  echo "Likely causes:"
  echo "  1. The version constraint references a version that does not exist."
  echo "     Check with: pnpm view <pkg>@<constraint> version"
  echo "  2. pnpm install was never run after adding the package."
  echo ""
  echo "Fix the version constraints, run 'cd $UI_DIR && pnpm install', then commit"
  echo "the updated package.json and pnpm-lock.yaml together."
  exit 1
else
  echo "PASS: All $PACKAGE_JSON dependencies are resolved in $LOCK_FILE."
  exit 0
fi
