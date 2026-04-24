"""JobPackage shared kernel.

Provides the shared contract between the Ingestion context (producer)
and the Extraction context (consumer). A JobPackage is a ZIP archive
containing a manifest, a changeset, raw content files (content-addressable),
and an adapter checkpoint snapshot.

Public API:
    - JobPackageBuilder: assembles a ZIP archive
    - JobPackageReader: reads and validates a ZIP archive
    - Value objects: JobPackageId, ContentRef, SyncMode, ChangeOperation,
                     ChangesetEntry, Manifest, AdapterCheckpoint
    - compute_content_checksum: content directory checksum computation
    - validate_zip_entry_name / PathSafetyError: path safety helpers
"""

from shared_kernel.job_package.builder import JobPackageBuilder
from shared_kernel.job_package.checksum import compute_content_checksum
from shared_kernel.job_package.path_safety import (
    PathSafetyError,
    validate_zip_entry_name,
)
from shared_kernel.job_package.reader import JobPackageReader
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    ContentRef,
    JobPackageId,
    Manifest,
    SyncMode,
)

__all__ = [
    # Builder / Reader
    "JobPackageBuilder",
    "JobPackageReader",
    # Value objects
    "AdapterCheckpoint",
    "ChangeOperation",
    "ChangesetEntry",
    "ContentRef",
    "JobPackageId",
    "Manifest",
    "SyncMode",
    # Utilities
    "compute_content_checksum",
    "PathSafetyError",
    "validate_zip_entry_name",
]
