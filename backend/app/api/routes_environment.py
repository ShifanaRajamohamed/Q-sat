"""Environment API endpoints with Scenario, MQTT, and Historical Replay support."""

from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from backend.app.models.environment import (
    EnvironmentData,
    HistoricalReplayConfig,
    HistoricalReplayStatus,
)
from backend.app.services.environment_service import environment_service

router = APIRouter(prefix="/api/environment", tags=["Environment"])


class SetModeRequest(BaseModel):
    mode: Literal["simulation", "mqtt", "historical_replay"] = Field(
        ..., description="Target operating mode"
    )


@router.get("/current", response_model=EnvironmentData, summary="Get current environmental conditions")
async def get_current_environment() -> EnvironmentData:
    """Return the latest environmental telemetry state vector.
    
    Includes temperature, humidity, ambient light, vibration, cloud factor,
    turbulence, provenance, and active mode (SIMULATION / HARDWARE / HISTORICAL_REPLAY).
    """
    return environment_service.get_current_environment()


@router.get("/mode", summary="Get current environment operating mode")
async def get_environment_mode():
    """Return whether the environment layer is running in simulation, mqtt, or historical_replay."""
    return {
        "mode": environment_service.mode,
        "is_healthy": environment_service.provider.is_healthy()
    }


@router.post("/mode", summary="Switch environment operating mode")
async def set_environment_mode(payload: SetModeRequest):
    """Switch environment between 'simulation', 'mqtt', and 'historical_replay'."""
    try:
        environment_service.set_mode(payload.mode)
        return {"status": "success", "mode": environment_service.mode}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/historical/files", summary="List available historical weather CSV files")
async def list_historical_files():
    """Return catalog of historical weather CSV files and their metadata."""
    files_info = environment_service.list_historical_files()
    filenames = [f["filename"] for f in files_info]
    return {
        "files": filenames,
        "details": files_info
    }


@router.post("/historical/configure", response_model=HistoricalReplayStatus, summary="Configure and activate historical weather replay")
async def configure_historical_replay(payload: HistoricalReplayConfig) -> HistoricalReplayStatus:
    """Load specified historical weather CSV and switch environment into historical replay mode."""
    try:
        return environment_service.configure_historical_replay(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to configure historical replay: {exc}")


@router.get("/historical/status", summary="Get status of active historical replay")
async def get_historical_status():
    """Return active replay metadata, time anchor, and interpolation status."""
    status = environment_service.get_historical_status()
    if status is None:
        return {
            "is_active": False,
            "mode": environment_service.mode,
            "message": "Historical replay is not currently active. Use POST /api/environment/historical/configure to activate."
        }
    return status
