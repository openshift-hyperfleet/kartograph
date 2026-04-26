"""Ingestion bounded context.

Responsible for extracting raw data from data sources via adapters
and packaging it into JobPackages for downstream processing.

Bounded context responsibilities:
- Running adapters to fetch Raw Content Changesets
- Packaging raw content and manifests into JobPackages (ZIP files)
- Publishing JobPackageProduced or IngestionFailed events to the outbox
"""
