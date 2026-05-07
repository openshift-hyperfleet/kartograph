"""Development utility routes.

These endpoints are for development/debugging only and should NOT be
exposed in production. Easy to remove by deleting this file and the
import in main.py.

Graph viewer endpoints have been promoted to the authenticated dev-ui
page at /graph/visualizer with data served via GET /graph/visualizer/data.
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/util", tags=["dev-utilities"])
