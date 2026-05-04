"""Ingestion bounded context.

Responsible for extracting raw data from external data sources via
adapters (e.g., GitHub, Kubernetes) and packaging the raw content
into JobPackages for downstream processing by the Extraction context.
"""
