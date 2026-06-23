"""Composition-root hook for advancing extraction baselines after successful runs."""

from __future__ import annotations

from typing import Awaitable, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    pass

AdvanceBaselines = Callable[..., Awaitable[int]]

_advancer: AdvanceBaselines | None = None


def register_extraction_baseline_advancer(advancer: AdvanceBaselines) -> None:
    """Register the Management-side baseline advancer at application startup."""
    global _advancer
    _advancer = advancer


def get_extraction_baseline_advancer() -> AdvanceBaselines | None:
    """Return the registered baseline advancer, if configured."""
    return _advancer
