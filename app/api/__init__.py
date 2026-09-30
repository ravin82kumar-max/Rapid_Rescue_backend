from app.api.emergency import router as emergency_router
from app.api.auth import router as auth_router
from app.api.driver import router as driver_router
from app.api.verification import router as verification_router
from app.api.admin import router as admin_router
from app.api.location import router as location_router
from app.api.dispatch import router as dispatch_router
from app.api.websocket import router as websocket_router
from app.api.ambulance import router as ambulance_router

__all__ = [
    "emergency_router",
    "auth_router",
    "driver_router",
    "verification_router",
    "admin_router",
    "location_router",
    "dispatch_router",
    "websocket_router",
    "ambulance_router",
]
