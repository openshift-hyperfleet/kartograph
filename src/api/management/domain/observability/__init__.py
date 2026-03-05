"""Management domain observability probes.

Domain probes following the Domain Oriented Observability pattern.
Each aggregate has a Protocol interface and a Default structlog implementation.

See: https://martinfowler.com/articles/domain-oriented-observability.html
"""

from __future__ import annotations

from management.domain.observability.data_source_probe import (
    DataSourceProbe,
    DefaultDataSourceProbe,
)
from management.domain.observability.knowledge_graph_probe import (
    DefaultKnowledgeGraphProbe,
    KnowledgeGraphProbe,
)

__all__ = [
    "DataSourceProbe",
    "DefaultDataSourceProbe",
    "DefaultKnowledgeGraphProbe",
    "KnowledgeGraphProbe",
]
