"""Extraction presentation layer.

HTTP/MCP routes for extraction session and operation workflows are defined
here as the bounded context expands.
"""

from fastapi import APIRouter

from extraction.presentation import routes

router = APIRouter(prefix="/extraction", tags=["extraction"])
router.include_router(routes.router)

__all__ = ["router"]

