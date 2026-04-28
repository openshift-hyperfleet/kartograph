"""Extraction bounded context.

Responsible for transforming raw content (JobPackages) into graph data
using AI-based entity and relationship extraction.

Bounded context responsibilities:
- Processing JobPackages from Ingestion
- Running the Claude Agent SDK to extract entities and relationships
- Running the Deterministic Processor for renames/deletes
- Producing MutationLogs of graph operations
"""
