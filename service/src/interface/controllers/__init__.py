from src.interface.controllers.health_controller import router as health_router
from src.interface.controllers.v1 import internal_vehicle_router, vehicle_router

__all__ = ["health_router", "internal_vehicle_router", "vehicle_router"]
