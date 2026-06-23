"""Load post-run mutation verdict artifacts from agentic-ci workspaces."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from extraction.infrastructure.extraction_job_workdir_layout import mutation_result_path


@dataclass(frozen=True)
class ExtractionMutationVerdict:
    """Structured outcome written by helpers/workload-mutations.sh apply."""

    action: str
    applied: bool
    operations_applied: int
    errors: tuple[str, ...]
    http_status: int | None = None
    valid: bool | None = None
    operation_count: int | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ExtractionMutationVerdict:
        return cls(
            action=str(payload.get("action") or ""),
            applied=bool(payload.get("applied")),
            operations_applied=int(payload.get("operations_applied") or 0),
            errors=tuple(str(item) for item in payload.get("errors") or []),
            http_status=int(payload["http_status"])
            if payload.get("http_status") is not None
            else None,
            valid=bool(payload["valid"]) if "valid" in payload else None,
            operation_count=int(payload["operation_count"])
            if payload.get("operation_count") is not None
            else None,
        )


def load_mutation_verdict(job_root: Path) -> ExtractionMutationVerdict | None:
    path = mutation_result_path(job_root)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return ExtractionMutationVerdict.from_dict(payload)


def require_successful_apply(job_root: Path) -> ExtractionMutationVerdict:
    """Post-agent gate: extraction jobs must apply at least one mutation."""
    verdict = load_mutation_verdict(job_root)
    if verdict is None:
        raise RuntimeError(
            "Extraction job finished without mutations/result.json. "
            "Run helpers/workload-mutations.sh apply on your JSONL batch before finishing."
        )
    if verdict.action != "apply":
        raise RuntimeError(
            f"Extraction job wrote mutations/result.json for action '{verdict.action}' "
            "but apply is required."
        )
    if not verdict.applied or verdict.operations_applied <= 0:
        detail = "; ".join(verdict.errors) or "operations_applied is 0"
        raise RuntimeError(f"Extraction job applied no graph mutations: {detail}")
    return verdict
