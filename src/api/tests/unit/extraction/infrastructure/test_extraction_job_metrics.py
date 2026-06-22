"""Unit tests for OTEL metric parsing for extraction jobs."""

from __future__ import annotations

import json
from pathlib import Path

from extraction.infrastructure.extraction_job_metrics import metrics_from_otel_log


def test_metrics_from_otel_log_sums_token_and_cost(tmp_path: Path) -> None:
    otel_log = tmp_path / "claude-otel.jsonl"
    payload = {
        "resourceMetrics": [
            {
                "scopeMetrics": [
                    {
                        "metrics": [
                            {
                                "name": "claude_code.token.usage",
                                "sum": {
                                    "dataPoints": [
                                        {
                                            "asDouble": 100,
                                            "attributes": [
                                                {
                                                    "key": "model",
                                                    "value": {"stringValue": "claude"},
                                                },
                                                {
                                                    "key": "type",
                                                    "value": {"stringValue": "input"},
                                                },
                                            ],
                                        },
                                        {
                                            "asDouble": 40,
                                            "attributes": [
                                                {
                                                    "key": "model",
                                                    "value": {"stringValue": "claude"},
                                                },
                                                {
                                                    "key": "type",
                                                    "value": {"stringValue": "output"},
                                                },
                                            ],
                                        },
                                    ]
                                },
                            },
                            {
                                "name": "claude_code.cost.usage",
                                "sum": {
                                    "dataPoints": [
                                        {
                                            "asDouble": 0.0123,
                                            "attributes": [
                                                {
                                                    "key": "model",
                                                    "value": {"stringValue": "claude"},
                                                },
                                            ],
                                        }
                                    ]
                                },
                            },
                        ]
                    }
                ]
            }
        ]
    }
    otel_log.write_text(
        json.dumps({"path": "/v1/metrics", "payload": payload}) + "\n",
        encoding="utf-8",
    )

    metrics = metrics_from_otel_log(otel_log)

    assert metrics["input_tokens"] == 100
    assert metrics["output_tokens"] == 40
    assert metrics["cost_usd"] == 0.0123
