#!/usr/bin/env bash
# check-frontend-lockfile-frozen.sh
#
# Verifies that pnpm-lock.yaml is in sync with package.json by running
# `pnpm install --frozen-lockfile`.
#
# WHY this is needed:
#   check-frontend-deps-resolve.sh uses grep to find package names in the
#   lockfile. That check produces FALSE NEGATIVES when a package is already
#   present as a TRANSITIVE dependency — the name appears in the lockfile, so
#   the grep passes, but the `specifiers:` section has no entry for the newly-
#   added direct dependency. `pnpm install --frozen-lockfile` fails in this
#   case even though grep does not flag it.
#
#   The authoritative test is running pnpm itself with --frozen-lockfile.
#
# Usage:
#   ./check-frontend-lockfile-frozen.sh [ui_dir]
#
# Exit 0  — lockfile is up to date with package.json.
# Exit 1  — lockfile is stale or absent (pnpm install --frozen-lockfile fails).

set -euo pipefail

UI_DIR="${1:-src/dev-ui}"

if [[ ! -f "$UI_DIR/package.json" ]]; then
  echo "No package.json found at $UI_DIR. Skipping lockfile check."
  exit 0
fi

if [[ ! -f "$UI_DIR/pnpm-lock.yaml" ]]; then
  echo "FAIL: $UI_DIR/pnpm-lock.yaml does not exist."
  echo ""
  echo "Every package.json change must be accompanied by the generated lockfile."
  echo "Run 'cd $UI_DIR && pnpm install' and commit the generated pnpm-lock.yaml"
  echo "in the SAME commit as the package.json change."
  exit 1
fi

if ! command -v pnpm &>/dev/null; then
  echo "WARN: pnpm is not installed. Cannot verify lockfile with --frozen-lockfile."
  echo "PASS: pnpm-lock.yaml exists (shallow check only)."
  exit 0
fi

echo "=== Verifying pnpm lockfile is in sync with package.json ==="
echo "    Running: pnpm install --frozen-lockfile in $UI_DIR"
echo ""

set +e
(cd "$UI_DIR" && pnpm install --frozen-lockfile 2>&1)
exit_code=$?
set -e

echo ""
if [[ $exit_code -eq 0 ]]; then
  echo "PASS: pnpm-lock.yaml is in sync with package.json."
  exit 0
else
  echo "FAIL: pnpm install --frozen-lockfile exited with code $exit_code."
  echo ""
  echo "The lockfile is stale — package.json was modified without running pnpm install."
  echo ""
  echo "Most likely cause: a devDependency was added to package.json but the lockfile"
  echo "was not regenerated. The package name may appear in the lockfile as a transitive"
  echo "dependency (causing check-frontend-deps-resolve.sh to pass), but its specifier"
  echo "entry is absent, so --frozen-lockfile fails."
  echo ""
  echo "Fix:"
  echo "  cd $UI_DIR"
  echo "  pnpm install"
  echo "  git add pnpm-lock.yaml package.json"
  echo "  git commit -m 'chore(dev-ui): regenerate pnpm lockfile'"
  exit 1
fi
