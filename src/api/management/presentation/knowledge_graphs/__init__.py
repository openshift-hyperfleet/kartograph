"""Knowledge Graph presentation layer."""

from __future__ import annotations

from fastapi import APIRouter

from management.presentation.knowledge_graphs.extraction_jobs_routes import (
    router as extraction_jobs_router,
)
from management.presentation.knowledge_graphs.routes import (
    router as knowledge_graphs_router,
)

router = APIRouter()
router.include_router(knowledge_graphs_router)
router.include_router(extraction_jobs_router)

__all__ = ["router"]
