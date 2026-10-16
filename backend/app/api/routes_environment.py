"""Environment API endpoints."""

from fastapi import APIRouter
from backend.app.models.environment import EnvironmentData
from backend.app.services.environment_service import environment_service

router = APIRouter(prefix="/api/environment", tags=["Environment"])


@router.get("/current", response_model=EnvironmentData, summary="Get current environmental conditions")
async def get_current_environment() -> EnvironmentData:
    """Return the latest environmental telemetry state vector.
    
    Includes temperature, humidity, ambient light, vibration, cloud factor,
    turbulence, provenance (SIMULATION / HARDWARE), and active scenario.
    """
    return environment_service.get_current_environment()
