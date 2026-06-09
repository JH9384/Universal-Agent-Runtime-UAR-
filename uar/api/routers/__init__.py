"""FastAPI routers for the consolidated UAR application."""

from fastapi import APIRouter

from .uor import router as _uor_router
from .burn_in import router as burn_in_router
from .certification import router as certification_router
from .mission_control import router as mission_control_router
from .replay_confidence import router as replay_confidence_router
from .replay_explorer import router as replay_explorer_router
from .runtime_health import router as runtime_health_router
from .topology import router as topology_router
from .operator_workflows import router as operator_workflows_router
from .fleet import router as fleet_router

# Preserve the existing public export consumed by uar.boot while allowing
# Trust Spine routes to be mounted without expanding boot wiring.
uor_router = APIRouter()

# Legacy operational routers keep runtime routes mounted but are excluded from
# OpenAPI until their broad dict response/body annotations are normalized.
uor_router.include_router(_uor_router, include_in_schema=False)

uor_router.include_router(replay_confidence_router)
uor_router.include_router(burn_in_router)
uor_router.include_router(runtime_health_router)
uor_router.include_router(certification_router)
uor_router.include_router(mission_control_router)
uor_router.include_router(replay_explorer_router)
uor_router.include_router(topology_router)
uor_router.include_router(operator_workflows_router)
uor_router.include_router(fleet_router, include_in_schema=False)

__all__ = [
    "uor_router",
    "replay_confidence_router",
    "burn_in_router",
    "runtime_health_router",
    "certification_router",
    "mission_control_router",
    "replay_explorer_router",
    "topology_router",
]
