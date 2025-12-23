"""Domain-oriented observability infrastructure.

This module provides domain probes following the Domain Oriented Observability
pattern described by Martin Fowler. Domain probes encapsulate instrumentation
details and provide a clean, domain-focused API for observability.

See: https://martinfowler.com/articles/domain-oriented-observability.html
"""

from shared_kernel.observability_context import ObservationContext
from infrastructure.observability.probes import (
    ConnectionProbe,
    DefaultConnectionProbe,
)

__all__ = [
    "ConnectionProbe",
    "DefaultConnectionProbe",
    "ObservationContext",
]
