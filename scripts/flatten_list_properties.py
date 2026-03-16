#!/usr/bin/env python3
"""Reads master_ontology.jsonl and converts all list-of-strings properties
to single concatenated strings using ' || ' as the delimiter.

Empty lists become empty strings.

Usage:
    python3 scripts/flatten_list_properties.py master_ontology.jsonl kg_final.jsonl
"""

import json
import sys

SEPARATOR = " || "


def flatten_lists(record: dict) -> dict:
    if record.get("op") != "CREATE" or "set_properties" not in record:
        return record

    props = record["set_properties"]
    for key, value in props.items():
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            props[key] = SEPARATOR.join(value)

    return record


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.jsonl> <output.jsonl>", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    converted_props: dict[str, int] = {}
    total_records = 0

    with open(input_path) as fin, open(output_path, "w") as fout:
        for line in fin:
            total_records += 1
            record = json.loads(line.strip())
            original_props = record.get("set_properties", {})

            list_keys = [
                k for k, v in original_props.items()
                if isinstance(v, list) and all(isinstance(i, str) for i in v)
            ] if record.get("op") == "CREATE" else []

            record = flatten_lists(record)
            fout.write(json.dumps(record) + "\n")

            for k in list_keys:
                label = record.get("label", "UNKNOWN")
                full_key = f"{label}.{k}"
                converted_props[full_key] = converted_props.get(full_key, 0) + 1

    print(f"Processed {total_records} records -> {output_path}")
    print(f"Converted {len(converted_props)} unique list-of-strings properties:")
    for key in sorted(converted_props):
        print(f"  {key}: {converted_props[key]} instances")


if __name__ == "__main__":
    main()
