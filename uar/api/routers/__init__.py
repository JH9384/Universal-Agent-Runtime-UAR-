"""FastAPI routers for the consolidated UAR application."""

from fastapi import APIRouter

from .uor import router as _uor_router
from .replay_confidence import router as replay_confidence_router

# Preserve the existing public export consumed by uar.boot while allowing
# Trust Spine routes to be mounted without expanding boot wiring.
uor_router = APIRouter()
uor_router.include_router(_uor_router)
uor_router.include_router(replay_confidence_router)

__all__ = ["uor_router", "replay_confidence_router"]
