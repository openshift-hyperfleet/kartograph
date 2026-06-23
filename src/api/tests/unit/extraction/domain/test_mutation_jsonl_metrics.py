"""Unit tests for mutation JSONL metrics parsing."""

from __future__ import annotations

from extraction.domain.mutation_jsonl_metrics import metrics_from_mutation_jsonl


def test_metrics_from_mutation_jsonl_counts_instance_operations() -> None:
    jsonl = "\n".join(
        [
            '{"op":"DEFINE","type":"node","label":"service"}',
            '{"op":"CREATE","type":"node","id":"service:abc","label":"service"}',
            '{"op":"UPDATE","type":"node","id":"service:abc","set_properties":{"name":"api"}}',
            '{"op":"DELETE","type":"node","id":"service:old"}',
            '{"op":"CREATE","type":"edge","id":"edge:1","label":"calls"}',
            '{"op":"UPDATE","type":"edge","id":"edge:1","set_properties":{"weight":2}}',
            '{"op":"DELETE","type":"edge","id":"edge:old"}',
        ]
    )

    metrics = metrics_from_mutation_jsonl(jsonl)

    assert metrics["entities_created"] == 1
    assert metrics["entities_modified"] == 1
    assert metrics["entities_deleted"] == 1
    assert metrics["relationships_created"] == 1
    assert metrics["relationships_modified"] == 1
    assert metrics["relationships_deleted"] == 1
    assert metrics["write_ops"] == 6
