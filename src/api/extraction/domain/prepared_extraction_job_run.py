"""Prepared extraction job workspace before long-running agent execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PreparedExtractionJobRun:
    """Host workdir and agent prompt materialized without holding a DB session."""

    workdir: Path
    prompt: str
