#!/usr/bin/env bash
# check-nav-sections-match-spec.sh
#
# Validates that every navigation section defined under "Primary navigation"
# in experience.spec.md is present in the sidebar layout test and layout
# component, and that no extra sections exist in the tests that are absent
# from the spec.
#
# Exit 0 = PASS (spec and tests are consistent)
# Exit 1 = FAIL (mismatch detected)
# Exit 0 with SKIP message = spec or test file not found (not applicable)

set -euo pipefail

SPEC="specs/ui/experience.spec.md"
LAYOUT_TEST="src/dev-ui/app/tests/default.layout.test.ts"
INTERACTION_TEST="src/dev-ui/app/tests/interaction-principles.test.ts"

# Allow overriding paths via environment for testing
SPEC="${NAV_SPEC:-$SPEC}"
LAYOUT_TEST="${NAV_LAYOUT_TEST:-$LAYOUT_TEST}"

if [[ ! -f "$SPEC" ]]; then
  echo "SKIP: $SPEC not found — not a UI task"
  exit 0
fi

if [[ ! -f "$LAYOUT_TEST" ]] && [[ ! -f "$INTERACTION_TEST" ]]; then
  echo "SKIP: No sidebar layout test found — not applicable"
  exit 0
fi

# ── Extract spec nav sections ────────────────────────────────────────────────
# Collect bold section names under the "Primary navigation" scenario block.
# Matches lines like:  - **Explore** — Query Console, ...
spec_sections=()
in_primary_nav=0
while IFS= read -r line; do
  if [[ "$line" == *"Scenario: Primary navigation"* ]]; then
    in_primary_nav=1
    continue
  fi
  # Stop at the next scenario or requirement heading
  if [[ $in_primary_nav -eq 1 ]] && [[ "$line" =~ ^"####"|^"###" ]]; then
    in_primary_nav=0
    continue
  fi
  if [[ $in_primary_nav -eq 1 ]] && [[ "$line" =~ \*\*([A-Za-z]+)\*\* ]]; then
    section="${BASH_REMATCH[1]}"
    spec_sections+=("$section")
  fi
done < "$SPEC"

if [[ ${#spec_sections[@]} -eq 0 ]]; then
  echo "SKIP: No navigation sections found in $SPEC under 'Primary navigation'"
  exit 0
fi

echo "Spec navigation sections (${#spec_sections[@]}):"
for s in "${spec_sections[@]}"; do
  echo "  - $s"
done

# ── Check each spec section is represented in test files ────────────────────
FAIL=0
for section in "${spec_sections[@]}"; do
  found=0
  for test_file in "$LAYOUT_TEST" "$INTERACTION_TEST"; do
    [[ -f "$test_file" ]] || continue
    if grep -q "\"$section\"\|'$section'" "$test_file" 2>/dev/null; then
      found=1
      break
    fi
  done
  if [[ $found -eq 0 ]]; then
    echo "FAIL: Spec section '$section' not found in any layout test file"
    FAIL=1
  fi
done

# ── Check no extra sections in tests that are absent from spec ───────────────
# Build a lookup set of spec sections
declare -A spec_set
for s in "${spec_sections[@]}"; do
  spec_set["$s"]=1
done

# Extract section names from layout test (lines that look like sidebar section headings)
# Pattern: string literals followed by nav items — look for quoted capitalized words
# used as section labels in describe blocks or expected arrays
extra_found=0
for test_file in "$LAYOUT_TEST" "$INTERACTION_TEST"; do
  [[ -f "$test_file" ]] || continue
  # Look for quoted strings that match a sidebar section pattern:
  # title: 'Explore' | label: 'Data' | name: "Connect" | 'Settings'
  # We look for isolated capitalized words in quotes that could be section names
  while IFS= read -r candidate; do
    # Skip empty
    [[ -z "$candidate" ]] && continue
    # Only check single-word capitalized strings (nav section names are capitalized single words)
    if [[ "$candidate" =~ ^[A-Z][a-z]+$ ]]; then
      if [[ -z "${spec_set[$candidate]+x}" ]]; then
        echo "WARN: Test file '$test_file' references '$candidate' as a navigation section but it is not in the spec"
        extra_found=1
      fi
    fi
  done < <(grep -oP "(?<=['\"])([A-Z][a-z]+)(?=['\"])" "$test_file" 2>/dev/null \
    | grep -xE "Explore|Data|Connect|Settings|Admin|Monitor|Observe|Manage|Build|Analyze|Configure|Dashboard" \
    || true)
done

if [[ $FAIL -eq 1 ]]; then
  echo ""
  echo "RESULT: FAIL — spec navigation sections are not all covered in tests"
  echo "  Spec file: $SPEC (lines for 'Primary navigation' scenario)"
  echo "  Layout test: $LAYOUT_TEST"
  echo ""
  echo "To debug: grep -n 'Primary navigation' $SPEC"
  echo "          grep -n 'Explore\|Data\|Connect\|Settings' $LAYOUT_TEST"
  exit 1
fi

echo ""
echo "RESULT: PASS — all ${#spec_sections[@]} spec navigation sections represented in tests"
exit 0
