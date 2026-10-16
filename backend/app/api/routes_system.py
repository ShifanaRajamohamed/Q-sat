"""System status and health routes for Q-SAT Adaptive Ground Station."""

import time
from datetime import datetime, timezone
from fastapi import APIRouter
from backend.app.config import settings
from backend.app.models.system import SystemHealthResponse, SystemStatusResponse

router = APIRouter(prefix="/api/system", tags=["System"])

_START_TIME = time.time()


@router.get("/status", response_model=SystemStatusResponse, summary="Get high-level system status")
async def get_system_status() -> SystemStatusResponse:
    """Return operational status and environment mode."""
    return SystemStatusResponse(
        system=settings.SYSTEM_NAME,
        status="online",
        environment_mode=settings.ENVIRONMENT_MODE,
        version=settings.VERSION,
    )


@router.get("/health", response_model=SystemHealthResponse, summary="Get detailed system health and telemetry")
async def get_system_health() -> SystemHealthResponse:
    """Return health details, server uptime, and active ground station configuration."""
    return SystemHealthResponse(
        system=settings.SYSTEM_NAME,
        status="online",
        environment_mode=settings.ENVIRONMENT_MODE,
        version=settings.VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        uptime_seconds=round(time.time() - _START_TIME, 2),
        ground_station={
            "latitude": settings.GROUND_STATION_LAT,
            "longitude": settings.GROUND_STATION_LON,
            "altitude_m": settings.GROUND_STATION_ALT,
            "min_elevation_deg": settings.MIN_ELEVATION,
        },
    )
