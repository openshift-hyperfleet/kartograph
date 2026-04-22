"""Management bounded context presentation layer.

Organizes presentation concerns by domain aggregate following vertical slicing
and DDD principles. Each aggregate package contains its own routes and models.
"""

from __future__ import annotations

from fastapi import APIRouter

from management.presentation import knowledge_graphs

router = APIRouter(
    prefix="/management",
    tags=["management"],
)

router.include_router(knowledge_graphs.router)

__all__ = ["router"]
