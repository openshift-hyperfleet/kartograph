"""Unit tests for graph write metrics parsed from applied mutation JSONL."""

from __future__ import annotations

import json
from pathlib import Path

from extraction.infrastructure.extraction_job_mutation_metrics import (
    metrics_from_mutation_jsonl,
    metrics_from_mutation_workdir,
)


def test_metrics_from_mutation_jsonl_counts_instance_operations() -> None:
    jsonl = "\n".join(
        [
            json.dumps(
                {
                    "op": "CREATE",
                    "type": "node",
                    "id": "adapter:abc",
                    "label": "Adapter",
                    "set_properties": {"slug": "a", "data_source_id": "ds"},
                }
            ),
            json.dumps(
                {
                    "op": "UPDATE",
                    "type": "node",
                    "id": "adapter:def",
                    "label": "Adapter",
                    "set_properties": {"description": "updated"},
                }
            ),
            json.dumps(
                {
                    "op": "CREATE",
                    "type": "edge",
                    "label": "deploys",
                    "source_id": "adapter:abc",
                    "target_id": "cluster:xyz",
                }
            ),
            json.dumps(
                {
                    "op": "DEFINE",
                    "type": "node",
                    "label": "Adapter",
                }
            ),
        ]
    )

    metrics = metrics_from_mutation_jsonl(jsonl)

    assert metrics["entities_created"] == 1
    assert metrics["entities_modified"] == 1
    assert metrics["relationships_created"] == 1
    assert metrics["relationships_modified"] == 0
    assert metrics["write_ops"] == 3


def test_metrics_from_mutation_workdir_reads_latest_jsonl(tmp_path: Path) -> None:
    mutations = tmp_path / "mutations"
    mutations.mkdir()
    (mutations / "batch.jsonl").write_text(
        json.dumps(
            {
                "op": "UPDATE",
                "type": "edge",
                "id": "edge:1",
                "label": "connects",
                "set_properties": {"weight": 2},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = metrics_from_mutation_workdir(tmp_path)

    assert metrics["relationships_modified"] == 1
    assert metrics["write_ops"] == 1
