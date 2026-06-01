"""Operator workflow routers — decomposed from operator_workflows.py."""

from fastapi import APIRouter

from .briefing import router as briefing_router
from .trust_explorer import router as trust_explorer_router
from .incidents import router as incidents_router
from .time_machine import router as time_machine_router
from .inbox import router as inbox_router
from .investigations import router as investigations_router
from .graph import router as graph_router
from .reports import router as reports_router
from .search import router as search_router
from .analytics import router as analytics_router
from .insights import router as insights_router

router = APIRouter()
router.include_router(briefing_router)
router.include_router(trust_explorer_router)
router.include_router(incidents_router)
router.include_router(time_machine_router)
router.include_router(inbox_router)
router.include_router(investigations_router)
router.include_router(graph_router)
router.include_router(reports_router)
router.include_router(search_router)
router.include_router(analytics_router)
router.include_router(insights_router)
