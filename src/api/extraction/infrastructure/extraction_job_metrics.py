"""Parse agentic-ci OTEL logs into extraction job metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def metrics_from_otel_log(otel_log: Path) -> dict[str, Any]:
    """Extract token and cost metrics from an agentic-ci OTEL JSONL log."""
    records: list[dict[str, Any]] = []
    if not otel_log.is_file():
        return _empty_metrics()
    try:
        with otel_log.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        return _empty_metrics()
    if not records:
        return _empty_metrics()

    from agentic_ci.otel import parse_metrics

    token_totals, cost_totals, _api_requests, _active_time = parse_metrics(records)
    input_tokens = int(
        sum(count for (_model, token_type), count in token_totals.items() if token_type == "input")
    )
    output_tokens = int(
        sum(count for (_model, token_type), count in token_totals.items() if token_type == "output")
    )
    cache_read_tokens = int(
        sum(
            count
            for (_model, token_type), count in token_totals.items()
            if token_type == "cacheRead"
        )
    )
    cache_creation_tokens = int(
        sum(
            count
            for (_model, token_type), count in token_totals.items()
            if token_type == "cacheCreation"
        )
    )
    cost_usd = float(sum(cost_totals.values()))
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "cost_usd": cost_usd,
        "entities_created": 0,
        "entities_modified": 0,
        "relationships_created": 0,
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "cost_usd": 0.0,
        "entities_created": 0,
        "entities_modified": 0,
        "relationships_created": 0,
    }
