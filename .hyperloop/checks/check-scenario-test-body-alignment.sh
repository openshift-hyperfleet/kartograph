#!/usr/bin/env bash
# check-scenario-test-body-alignment.sh
#
# Detects test groups whose label matches a spec scenario name but whose
# assertion bodies only exercise guard conditions from OTHER scenarios
# rather than the named scenario's own behavior.
#
# Root cause of task-045 FAIL: The test group labeled "Knowledge graph
# selection" contained only `expect(...).toContain('No tenant selected')` —
# a guard assertion for a DIFFERENT scenario — while the actual KG selector
# UI and API scoping were never implemented or tested.
# check-frontend-scenario-labels.sh passed (the label existed) but the
# scenario behavior was entirely absent.
#
# Algorithm:
#   1. Extract scenario names from spec ("#### Scenario: <name>").
#   2. For each scenario, find the matching describe/it block in the test file.
#   3. Extract assertion strings (toContain/toBe/toEqual arg text) in that block.
#   4. Check whether assertion strings overlap with keywords from the scenario label.
#   5. If ALL assertions are pure guard phrases ("No tenant", "No workspace",
#      "Select a", "No knowledge graph selected", etc.) with NO overlap with
#      the scenario's own keywords, flag as POTENTIALLY MISALIGNED.
#
# Usage:
#   ./check-scenario-test-body-alignment.sh <spec-file> <test-file> [test-file...]
#
# Exit 0 — no misaligned test groups found.
# Exit 1 — one or more test groups appear to test a different scenario.

set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "PASS: No spec file or test files provided — nothing to check."
  echo "Usage: $0 <spec-file> <test-file> [test-file ...]"
  exit 0
fi

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <spec-file> <test-file> [test-file ...]"
  exit 1
fi

SPEC_FILE="$1"
shift
TEST_FILES=("$@")

if [[ "$SPEC_FILE" != "/dev/stdin" && ! -f "$SPEC_FILE" ]]; then
  echo "FAIL: Spec file not found: $SPEC_FILE"
  exit 1
fi

for tf in "${TEST_FILES[@]}"; do
  if [[ ! -f "$tf" ]]; then
    echo "FAIL: Test file not found: $tf"
    exit 1
  fi
done

echo "=== Checking scenario test body alignment ==="
echo "    Spec : $SPEC_FILE"
for tf in "${TEST_FILES[@]}"; do
  echo "    Test : $tf"
done
echo ""

python3 - "$SPEC_FILE" "${TEST_FILES[@]}" <<'PYEOF'
import re
import sys

SPEC_FILE = sys.argv[1]
TEST_FILES = sys.argv[2:]

# Guard phrases that belong to precondition/other-scenario guards,
# NOT to any specific spec scenario's own behavior.
GUARD_PHRASES = [
    "no tenant",
    "no workspace",
    "no knowledge graph",
    "select a tenant",
    "select a workspace",
    "select a knowledge graph",
    "please select",
    "not selected",
    "no selection",
    "loading...",
    "empty state",
]

# Stopwords stripped from scenario labels when building keyword sets.
STOPWORDS = {
    "a", "an", "the", "for", "in", "of", "with", "without", "via",
    "using", "when", "before", "after", "and", "or", "not", "to",
    "by", "on", "at", "from", "is", "are", "be", "has", "have",
    "its", "it", "that", "this", "which", "than", "as", "all",
    "any", "no", "until",
}


def extract_scenario_names(spec_path: str) -> list[str]:
    """Extract scenario names from '#### Scenario: <name>' headers."""
    if spec_path == "/dev/stdin":
        content = sys.stdin.read()
    else:
        with open(spec_path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    names = []
    for m in re.finditer(r"^#{1,4}\s*Scenario:\s+(.+)$", content, re.MULTILINE):
        names.append(m.group(1).strip())
    return names


def scenario_keywords(label: str) -> set[str]:
    """Return meaningful keywords from a scenario label."""
    tokens = re.sub(r"[^a-z0-9\s]", " ", label.lower()).split()
    return {t for t in tokens if t not in STOPWORDS and len(t) > 2}


def extract_describe_body(test_content: str, scenario_label: str) -> str | None:
    """
    Heuristically extract the body of the first describe/it block whose
    label contains the scenario_label (case-insensitive).

    Returns the block content (lines between the opening brace and matching
    closing brace at the same depth), or None if not found.
    """
    label_lower = scenario_label.lower()
    lines = test_content.splitlines()

    start_line = None
    for i, line in enumerate(lines):
        # Match describe('...', ...) or it('...', ...) containing the label
        if re.search(r"describe\s*\(|it\s*\(|test\s*\(", line):
            if label_lower in line.lower():
                start_line = i
                break

    if start_line is None:
        return None

    # Find the opening brace on or after start_line.
    depth = 0
    body_lines = []
    in_body = False

    for line in lines[start_line:]:
        opens = line.count("{") - line.count("\\{")
        closes = line.count("}") - line.count("\\}")
        if not in_body:
            if opens > 0:
                depth += opens - closes
                in_body = True
                # Don't include the opening-brace line itself, just body
                body_lines.append(line)
            continue
        depth += opens - closes
        body_lines.append(line)
        if depth <= 0:
            break

    return "\n".join(body_lines)


def extract_assertion_strings(block: str) -> list[str]:
    """
    Extract string literal arguments from expect-related calls.
    Catches patterns like:
      toContain('...') / toContain("...") / toBe('...') / toEqual('...')
      toHaveTextContent('...')
    """
    pattern = r'(?:toContain|toBe|toEqual|toHaveTextContent|toHaveBeenCalledWith|toMatch)\s*\(\s*[\'"]([^\'"]+)[\'"]'
    return re.findall(pattern, block, re.IGNORECASE)


def is_pure_guard(assertion_strings: list[str]) -> bool:
    """
    Return True if ALL assertion strings are recognisable guard phrases,
    with no scenario-specific content whatsoever.
    """
    if not assertion_strings:
        return False  # No string assertions — may use component assertions; don't flag
    for s in assertion_strings:
        s_lower = s.lower()
        is_guard = any(phrase in s_lower for phrase in GUARD_PHRASES)
        if not is_guard:
            return False  # At least one non-guard assertion found
    return True


def has_keyword_overlap(assertion_strings: list[str], keywords: set[str]) -> bool:
    """
    Return True if at least one assertion string contains at least one
    keyword from the scenario label.
    """
    combined = " ".join(assertion_strings).lower()
    return any(kw in combined for kw in keywords)


def main():
    scenario_names = extract_scenario_names(SPEC_FILE)
    if not scenario_names:
        print("PASS: No scenario headers found in spec — nothing to check.")
        sys.exit(0)

    misaligned = []

    for scenario in scenario_names:
        keywords = scenario_keywords(scenario)

        for test_file in TEST_FILES:
            with open(test_file, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()

            # Check the scenario label exists at all (prerequisite for this check)
            if scenario.lower() not in content.lower():
                continue  # check-frontend-scenario-labels.sh handles missing labels

            block = extract_describe_body(content, scenario)
            if block is None:
                continue  # Label found but not in a describe/it — skip

            assertion_strings = extract_assertion_strings(block)

            # Only flag when:
            # (a) ALL string assertions are guard phrases AND
            # (b) NONE of those strings overlap with the scenario's own keywords
            if is_pure_guard(assertion_strings) and not has_keyword_overlap(
                assertion_strings, keywords
            ):
                misaligned.append(
                    {
                        "scenario": scenario,
                        "file": test_file,
                        "assertions": assertion_strings,
                        "keywords": keywords,
                    }
                )
                break  # Only report once per scenario across all test files

    if misaligned:
        print(
            f"FAIL: {len(misaligned)} test group(s) appear to assert on guard "
            f"conditions from OTHER scenarios rather than the labeled scenario:\n"
        )
        for item in misaligned:
            print(f"  Scenario : \"{item['scenario']}\"")
            print(f"  File     : {item['file']}")
            print(f"  Assertions found:")
            for a in item["assertions"]:
                print(f"    - \"{a}\"")
            print(f"  Expected keyword(s) in at least one assertion: "
                  f"{sorted(item['keywords'])}")
            print(
                "\n  The test group label implies testing the named scenario, but "
                "ALL its\n  string assertions are guard-condition text from other "
                "scenarios.\n  Add assertions that directly exercise this scenario's "
                "THEN clause:\n"
                "    - Verify the required UI component exists\n"
                "    - Verify the guard/disabled state specified\n"
                "    - Verify the API call parameters specified\n"
            )
            print()
        print(
            "check-frontend-scenario-labels.sh passes when a label exists, but "
            "it cannot\ndetect assertions that belong to a different scenario. "
            "This check fills that gap."
        )
        sys.exit(1)
    else:
        print(
            f"PASS: All {len(scenario_names)} scenario(s) with test groups have "
            f"body-level alignment."
        )
        sys.exit(0)


main()
PYEOF
