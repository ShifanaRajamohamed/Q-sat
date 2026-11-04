"""Satellite telemetry, orbital tracking, and ground station API routes."""

from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.models.satellite import GroundStationConfig, SatelliteState
from backend.app.services.satellite_service import satellite_service

router = APIRouter(prefix="/api/satellite", tags=["Satellite"])


class OrbitModeRequest(BaseModel):
    mode: Literal["reference_pass", "tle_prediction"] = Field(
        ..., description="Orbital mode: 'reference_pass' (analytical) or 'tle_prediction' (SGP4/Skyfield)"
    )


class TLESelectRequest(BaseModel):
    satellite_key: str = Field(..., description="Documented reference satellite key (e.g., 'MICIUS', 'ISS')")


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


@router.get("/mode", summary="Get active orbital tracking mode")
async def get_orbit_mode() -> Dict[str, str]:
    """Return current orbital tracking mode: 'reference_pass' or 'tle_prediction'."""
    return {"orbit_mode": satellite_service.orbit_mode}


@router.post("/mode", summary="Switch orbital tracking mode")
async def set_orbit_mode(req: OrbitModeRequest) -> Dict[str, str]:
    """Switch between reference pass mode and SGP4 TLE orbital tracking."""
    mode = satellite_service.set_orbit_mode(req.mode)
    return {"status": "success", "orbit_mode": mode}


@router.get("/tle/satellites", summary="List documented reference satellites for SGP4 tracking")
async def list_tle_satellites() -> List[Dict[str, Any]]:
    """Return list of documented reference satellites with epochs, sources, and assumed payload parameters."""
    return satellite_service.list_reference_satellites()


@router.post("/tle/select", summary="Select active TLE reference satellite")
async def select_tle_satellite(req: TLESelectRequest) -> Dict[str, Any]:
    """Select active reference satellite for SGP4 orbital tracking."""
    try:
        return satellite_service.select_tle_satellite(req.satellite_key)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/tle/predict-passes", summary="Predict upcoming optical passes over ground station")
async def predict_upcoming_passes(hours: float = Query(24.0, ge=1.0, le=168.0)) -> List[Dict[str, Any]]:
    """Calculate predicted optical visibility windows (AOS, TCA, LOS) over Tiruchirappalli reference ground station."""
    return satellite_service.predict_passes(hours=hours)
