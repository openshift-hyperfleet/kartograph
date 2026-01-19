"""AGE bulk loading package.

Provides optimized bulk loading for Apache AGE using PostgreSQL's COPY protocol
and direct SQL INSERT/UPDATE operations.

Public API:
    - AgeBulkLoadingStrategy: Main bulk loading orchestrator
    - AgeIndexingStrategy: Transactional index creation for AGE labels
    - validate_label_name: Label name validation utility
    - compute_stable_hash: Stable hash for advisory locks
"""

from .indexing import AgeIndexingStrategy
from .strategy import AgeBulkLoadingStrategy
from .utils import compute_stable_hash, validate_label_name

__all__ = [
    "AgeBulkLoadingStrategy",
    "AgeIndexingStrategy",
    "validate_label_name",
    "compute_stable_hash",
]
