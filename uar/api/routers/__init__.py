"""FastAPI routers for the consolidated UAR application."""

from fastapi import APIRouter

from .uor import router as _uor_router
from .burn_in import router as burn_in_router
from .certification import router as certification_router
from .mission_control import router as mission_control_router
from .replay_confidence import router as replay_confidence_router
from .replay_explorer import router as replay_explorer_router
from .runtime_health import router as runtime_health_router

# Preserve the existing public export consumed by uar.boot while allowing
# Trust Spine routes to be mounted without expanding boot wiring.
uor_router = APIRouter()
uor_router.include_router(_uor_router)
uor_router.include_router(replay_confidence_router)
uor_router.include_router(burn_in_router)
uor_router.include_router(runtime_health_router)
uor_router.include_router(certification_router)
uor_router.include_router(mission_control_router)
uor_router.include_router(replay_explorer_router)

__all__ = [
    "uor_router",
    "replay_confidence_router",
    "burn_in_router",
    "runtime_health_router",
    "certification_router",
    "mission_control_router",
    "replay_explorer_router",
]
