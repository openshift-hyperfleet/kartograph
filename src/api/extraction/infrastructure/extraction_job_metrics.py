"""Parse agentic-ci OTEL logs and Claude stream output into extraction job metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from extraction.infrastructure.extraction_job_mutation_metrics import (
    applied_mutation_jsonl_from_workdir,
    metrics_from_mutation_workdir,
)
from extraction.infrastructure.job_mutation_artifact_store import read_instance_changes_from_workdir


def merge_extraction_job_metrics(
    *,
    otel_log: Path | None,
    workdir: Path,
    activity_log: Path | None = None,
) -> dict[str, Any]:
    """Combine OTEL token metrics, Claude stream fallback, and applied JSONL graph writes."""
    metrics = metrics_from_otel_log(otel_log) if otel_log is not None else _empty_metrics()
    if _token_total(metrics) == 0:
        stream_log = workdir / "agent_stream.jsonl"
        stream_metrics = metrics_from_claude_stream_log(stream_log)
        if not stream_metrics and activity_log is not None:
            stream_metrics = metrics_from_claude_stream_log(activity_log)
        for key, value in stream_metrics.items():
            if key.startswith(("input_", "output_", "cache_", "cost_")) and value:
                metrics[key] = value

    mutation_metrics = metrics_from_mutation_workdir(workdir)
    metrics.update(mutation_metrics)
    applied_jsonl = applied_mutation_jsonl_from_workdir(workdir)
    if applied_jsonl:
        metrics["applied_mutations_jsonl"] = applied_jsonl
    instance_changes_jsonl = read_instance_changes_from_workdir(workdir)
    if instance_changes_jsonl:
        metrics["applied_instance_changes_jsonl"] = instance_changes_jsonl
    return metrics


def metrics_from_claude_stream_log(activity_log: Path) -> dict[str, Any]:
    """Extract token usage from claude-code JSONL result events in the activity log."""
    if not activity_log.is_file():
        return {}
    usage: dict[str, Any] = {}
    cost_usd = 0.0
    for line in activity_log.read_text(encoding="utf-8").splitlines():
        body = line.strip()
        if " " in body and body[0].isdigit() and "T" in body.split(" ", 1)[0]:
            _, _, body = body.partition(" ")
        body = body.strip()
        if not body.startswith("{"):
            continue
        try:
            event = json.loads(body)
        except json.JSONDecodeError:
            continue
        if str(event.get("type") or "") != "result":
            continue
        raw_usage = event.get("usage")
        if isinstance(raw_usage, dict):
            usage = raw_usage
        total_cost = event.get("total_cost_usd")
        if total_cost is not None:
            cost_usd = float(total_cost)

    if not usage and cost_usd == 0.0:
        return {}

    return {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "cache_read_tokens": int(usage.get("cache_read_input_tokens") or 0),
        "cache_creation_tokens": int(usage.get("cache_creation_input_tokens") or 0),
        "cost_usd": cost_usd,
    }


def _token_total(metrics: dict[str, Any]) -> int:
    return int(metrics.get("input_tokens") or 0) + int(metrics.get("output_tokens") or 0)


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
        "relationships_modified": 0,
        "write_ops": 0,
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
        "relationships_modified": 0,
        "write_ops": 0,
    }
