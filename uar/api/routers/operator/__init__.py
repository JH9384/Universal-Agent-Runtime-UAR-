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
from .sync import router as sync_router
from .plugins import router as plugins_router
from .credentials import router as credentials_router
from .maintenance import router as maintenance_router
from .activity import router as activity_router
from .file_types import router as file_types_router
from .data_sources import router as data_sources_router
from .alerts import router as alerts_router
from .circuit_breakers import router as circuit_breakers_router
from .metrics import router as admin_metrics_router
from .updates import router as updates_router

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
router.include_router(sync_router)
router.include_router(plugins_router)
router.include_router(credentials_router)
router.include_router(maintenance_router)
router.include_router(activity_router)
router.include_router(file_types_router)
router.include_router(data_sources_router)
router.include_router(alerts_router)
router.include_router(circuit_breakers_router)
router.include_router(admin_metrics_router)
router.include_router(updates_router)
