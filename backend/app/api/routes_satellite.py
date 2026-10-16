"""Satellite telemetry and ground station API routes."""

from fastapi import APIRouter
from backend.app.models.satellite import GroundStationConfig, SatelliteState
from backend.app.services.satellite_service import satellite_service

router = APIRouter(prefix="/api/satellite", tags=["Satellite"])


@router.get("/state", response_model=SatelliteState, summary="Get current satellite orbital and tracking state")
async def get_satellite_state() -> SatelliteState:
    """Return real-time topocentric telemetry: altitude, elevation, azimuth, slant range, velocity, and visibility."""
    return satellite_service.get_state()


@router.get("/ground_station", response_model=GroundStationConfig, summary="Get ground station configuration")
async def get_ground_station() -> GroundStationConfig:
    """Return active optical ground station coordinates and minimum elevation threshold."""
    return satellite_service.get_ground_station()


@router.post("/ground_station", response_model=GroundStationConfig, summary="Update ground station configuration")
async def update_ground_station(config: GroundStationConfig) -> GroundStationConfig:
    """Update ground station coordinates and recalculate pass geometry."""
    satellite_service.update_ground_station(config)
    return satellite_service.get_ground_station()
