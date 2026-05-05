#!/usr/bin/env bash
# check-spec-and-condition-coverage.sh
#
# Detects scenarios where the spec's THEN block contains "- AND" conditions
# that have no keyword coverage in the corresponding test describe block.
#
# Root cause of task-141 FAIL: The "Individual type editing" scenario had three
# THEN conditions:
#   - THEN they can modify the label, description, required properties, and optional properties
#   - AND they can add or remove relationship types
#   - AND they can specify exact property requirements
#
# The implementer covered only the first THEN condition. Both AND conditions
# were absent from the implementation AND from the tests. check-frontend-scenario-
# labels.sh passed (the scenario name appeared in the test file) and
# check-scenario-test-body-alignment.sh passed (keyword overlap existed for the
# first THEN), but neither check inspects AND-condition coverage individually.
#
# Algorithm:
#   1. Extract scenarios from spec ("#### Scenario: <name>").
#   2. For each scenario, collect the THEN block: the line starting with "- THEN"
#      and all immediately-following "- AND" lines.
#   3. For each "- AND" condition, extract keywords (≥4 chars, non-stopword).
#   4. Find the matching describe/it block in the test files.
#   5. Check whether the block body contains AT LEAST ONE keyword from each
#      AND condition.
#   6. Flag any AND condition with zero keyword hits as MISSING.
#
# Usage:
#   ./check-spec-and-condition-coverage.sh <spec-file> <test-file> [test-file ...]
#
# Exit 0 — all AND conditions in every THEN block have keyword coverage.
# Exit 1 — one or more AND conditions have no coverage in any test file.

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

# If spec is piped via /dev/stdin, capture it to a temp file before spawning
# Python (the Python heredoc consumes Python3's stdin, so sys.stdin.read() inside
# Python would return empty).  Writing to a temp file normalises both call paths.
SPEC_TMPFILE=""
if [[ "$SPEC_FILE" == "/dev/stdin" ]]; then
  SPEC_TMPFILE="$(mktemp /tmp/check-and-conditions-spec.XXXXXX)"
  cat /dev/stdin > "$SPEC_TMPFILE"
  SPEC_FILE="$SPEC_TMPFILE"
  trap 'rm -f "$SPEC_TMPFILE"' EXIT
elif [[ ! -f "$SPEC_FILE" ]]; then
  echo "FAIL: Spec file not found: $SPEC_FILE"
  exit 1
fi

for tf in "${TEST_FILES[@]}"; do
  if [[ ! -f "$tf" ]]; then
    echo "FAIL: Test file not found: $tf"
    exit 1
  fi
done

echo "=== Checking spec AND-condition coverage in tests ==="
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

# Stopwords stripped when building keyword sets from AND conditions.
STOPWORDS = {
    "a", "an", "the", "for", "in", "of", "with", "without", "via",
    "using", "when", "before", "after", "and", "or", "not", "to",
    "by", "on", "at", "from", "is", "are", "be", "has", "have",
    "its", "it", "that", "this", "which", "than", "as", "all",
    "any", "no", "until", "they", "can", "must", "their", "than",
    "also", "such", "e.g", "etc", "will", "should", "would", "may",
    "into", "out", "been", "were", "was", "then", "than", "how",
    "each", "per", "both",
}
# Minimum keyword length to be meaningful
MIN_KW_LEN = 4


def read_spec(spec_path: str) -> str:
    if spec_path == "/dev/stdin":
        return sys.stdin.read()
    with open(spec_path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def extract_scenarios_with_then_blocks(spec_content: str) -> list[dict]:
    """
    Returns a list of dicts:
      {
        "name": str,                  # scenario name
        "then_line": str | None,      # the THEN condition text
        "and_conditions": [str],      # list of AND condition texts
      }
    """
    lines = spec_content.splitlines()
    scenarios = []
    current_scenario = None
    in_then_block = False

    for line in lines:
        # Detect scenario header
        m = re.match(r"^#{1,4}\s*Scenario:\s+(.+)$", line.strip())
        if m:
            if current_scenario is not None:
                scenarios.append(current_scenario)
            current_scenario = {
                "name": m.group(1).strip(),
                "then_line": None,
                "and_conditions": [],
            }
            in_then_block = False
            continue

        # Detect any new header (ends previous scenario's THEN block)
        if re.match(r"^#{1,4}\s+\S", line.strip()) and current_scenario is not None:
            in_then_block = False
            continue

        if current_scenario is None:
            continue

        stripped = line.strip()

        # Detect THEN line
        if re.match(r"^-\s+THEN\s+", stripped, re.IGNORECASE):
            then_text = re.sub(r"^-\s+THEN\s+", "", stripped, flags=re.IGNORECASE).strip()
            current_scenario["then_line"] = then_text
            in_then_block = True
            continue

        # Detect AND lines immediately following THEN
        if in_then_block and re.match(r"^-\s+AND\s+", stripped, re.IGNORECASE):
            and_text = re.sub(r"^-\s+AND\s+", "", stripped, flags=re.IGNORECASE).strip()
            current_scenario["and_conditions"].append(and_text)
            continue

        # Any non-THEN/AND list item ends the THEN block
        if in_then_block and stripped.startswith("-"):
            in_then_block = False

    if current_scenario is not None:
        scenarios.append(current_scenario)

    return scenarios


def condition_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from a condition string."""
    # Remove example text in parentheses/quotes
    text = re.sub(r'\(.*?\)', ' ', text)
    text = re.sub(r'"[^"]*"', ' ', text)
    text = re.sub(r"'[^']*'", ' ', text)
    tokens = re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()
    return {t for t in tokens if t not in STOPWORDS and len(t) >= MIN_KW_LEN}


def extract_describe_body(content: str, scenario_label: str) -> str | None:
    """
    Heuristically extract the body of the first describe/it/test block
    whose label contains the scenario_label (case-insensitive).
    """
    label_lower = scenario_label.lower()
    lines = content.splitlines()
    start_line = None
    for i, line in enumerate(lines):
        if re.search(r"describe\s*\(|it\s*\(|test\s*\(", line):
            if label_lower in line.lower():
                start_line = i
                break

    if start_line is None:
        return None

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
                body_lines.append(line)
            continue
        depth += opens - closes
        body_lines.append(line)
        if depth <= 0:
            break

    return "\n".join(body_lines)


def condition_covered_in_block(and_text: str, block: str) -> bool:
    """
    Return True if at least one keyword from the AND condition appears
    in the test block body.
    """
    keywords = condition_keywords(and_text)
    if not keywords:
        return True  # no meaningful keywords — cannot validate
    block_lower = block.lower()
    return any(kw in block_lower for kw in keywords)


def main():
    spec_content = read_spec(SPEC_FILE)
    scenarios = extract_scenarios_with_then_blocks(spec_content)

    # Filter to scenarios that have at least one AND condition
    scenarios_with_and = [s for s in scenarios if s["and_conditions"]]

    if not scenarios_with_and:
        print("PASS: No scenarios with AND conditions found — nothing to check.")
        sys.exit(0)

    print(f"Found {len(scenarios_with_and)} scenario(s) with AND conditions.\n")

    failures = []

    for scenario in scenarios_with_and:
        name = scenario["name"]
        and_conditions = scenario["and_conditions"]

        # Gather all test file content for this scenario
        combined_block = ""
        for test_file in TEST_FILES:
            with open(test_file, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            if name.lower() not in content.lower():
                continue
            block = extract_describe_body(content, name)
            if block:
                combined_block += "\n" + block

        if not combined_block:
            # Scenario label not found in any test file — handled by
            # check-frontend-scenario-labels.sh; skip here to avoid double-reporting.
            print(f"  SKIP (no test block found) : {name}")
            continue

        scenario_failures = []
        for and_text in and_conditions:
            covered = condition_covered_in_block(and_text, combined_block)
            keywords = condition_keywords(and_text)
            status = "COVERED" if covered else "MISSING"
            print(f"  {status:7s} [{name}] AND {and_text}")
            if not covered:
                scenario_failures.append({
                    "and_text": and_text,
                    "keywords": sorted(keywords),
                })

        if scenario_failures:
            failures.append({
                "scenario": name,
                "missing": scenario_failures,
            })

    print()

    if failures:
        total_missing = sum(len(f["missing"]) for f in failures)
        print(f"FAIL: {total_missing} AND condition(s) in {len(failures)} scenario(s) "
              f"have no keyword coverage in the test describe block.\n")
        for f in failures:
            print(f"  Scenario: \"{f['scenario']}\"")
            for m in f["missing"]:
                print(f"    Missing AND condition : {m['and_text']}")
                print(f"    Expected keywords     : {m['keywords']}")
                print()
        print("Each '- AND' line in a scenario THEN block is a SEPARATE requirement.")
        print("The describe block for that scenario must contain at least one of the")
        print("AND condition's keywords so that removing the production code for that")
        print("condition would cause the test to fail.")
        print()
        print("Steps to fix:")
        print("  1. Implement the missing AND condition in the production code.")
        print("  2. Add an assertion in the scenario's test block that exercises it.")
        print("  3. Re-run this script to confirm exit 0.")
        sys.exit(1)
    else:
        covered_count = sum(len(s["and_conditions"]) for s in scenarios_with_and)
        print(f"PASS: All {covered_count} AND condition(s) across "
              f"{len(scenarios_with_and)} scenario(s) have keyword coverage.")
        sys.exit(0)


main()
PYEOF
