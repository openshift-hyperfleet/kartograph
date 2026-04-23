"""Management presentation layer."""

from __future__ import annotations

from fastapi import APIRouter

from management.presentation import data_sources, knowledge_graphs

router = APIRouter(prefix="/management", tags=["management"])
router.include_router(knowledge_graphs.router)
router.include_router(data_sources.router)

__all__ = ["router"]
