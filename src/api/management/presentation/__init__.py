"""Management presentation layer.

Aggregates sub-routers for knowledge graphs and data sources,
exporting a single management_router for registration in main.py.
"""

from __future__ import annotations

from fastapi import APIRouter

from management.presentation.data_sources.routes import router as ds_router
from management.presentation.knowledge_graphs.routes import router as kg_router

management_router = APIRouter(
    prefix="/management",
    tags=["management"],
)

management_router.include_router(kg_router)
management_router.include_router(ds_router)

__all__ = ["management_router"]
