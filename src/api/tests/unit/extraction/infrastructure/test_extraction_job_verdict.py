"""Unit tests for extraction job mutation verdict post-gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from extraction.infrastructure.extraction_job_verdict import (
    load_mutation_verdict,
    require_successful_apply,
)


def test_require_successful_apply_accepts_apply_verdict(tmp_path: Path) -> None:
    result_path = tmp_path / "mutations" / "result.json"
    result_path.parent.mkdir(parents=True)
    result_path.write_text(
        json.dumps(
            {
                "action": "apply",
                "applied": True,
                "operations_applied": 3,
                "errors": [],
                "http_status": 200,
            }
        ),
        encoding="utf-8",
    )

    verdict = require_successful_apply(tmp_path)

    assert verdict.operations_applied == 3


def test_require_successful_apply_rejects_missing_verdict(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="mutations/result.json"):
        require_successful_apply(tmp_path)


def test_require_successful_apply_rejects_zero_operations(tmp_path: Path) -> None:
    result_path = tmp_path / "mutations" / "result.json"
    result_path.parent.mkdir(parents=True)
    result_path.write_text(
        json.dumps(
            {
                "action": "apply",
                "applied": True,
                "operations_applied": 0,
                "errors": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="applied no graph mutations"):
        require_successful_apply(tmp_path)


def test_load_mutation_verdict_parses_payload(tmp_path: Path) -> None:
    result_path = tmp_path / "mutations" / "result.json"
    result_path.parent.mkdir(parents=True)
    result_path.write_text(
        json.dumps({"action": "validate", "valid": True, "operation_count": 2, "errors": []}),
        encoding="utf-8",
    )

    verdict = load_mutation_verdict(tmp_path)

    assert verdict is not None
    assert verdict.valid is True
    assert verdict.operation_count == 2
