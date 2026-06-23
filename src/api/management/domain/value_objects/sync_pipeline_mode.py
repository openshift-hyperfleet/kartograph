"""Sync pipeline mode — controls how far a sync run progresses."""

from typing import Literal

SyncPipelineMode = Literal["full", "ingest_only"]

DEFAULT_SYNC_PIPELINE_MODE: SyncPipelineMode = "full"
