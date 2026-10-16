"""Simulation control and scenario management API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Query
from backend.app.models.environment import (
    EnvironmentData,
    ScenarioInfo,
    SetScenarioRequest,
    SimulationStepRequest,
)
from backend.app.services.environment_service import environment_service

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])


@router.get("/scenarios", response_model=List[ScenarioInfo], summary="List available benchmark scenarios")
async def get_scenarios() -> List[ScenarioInfo]:
    """Retrieve metadata and physical profiles for all benchmark simulation scenarios (A–F)."""
    return environment_service.get_available_scenarios()


@router.post("/scenario", response_model=EnvironmentData, summary="Switch active simulation scenario")
async def set_scenario(payload: SetScenarioRequest) -> EnvironmentData:
    """Switch active environmental scenario (e.g., CLEAR_SKY, HUMID, CLOUDY, VIBRATION, etc.)."""
    return environment_service.set_scenario(payload.scenario, seed=payload.seed)


@router.post("/step", response_model=EnvironmentData, summary="Advance simulation by dt seconds")
async def step_simulation(payload: SimulationStepRequest) -> EnvironmentData:
    """Manually step the simulation forward and return the new environment state."""
    return environment_service.step(dt=payload.dt)


@router.post("/reset", response_model=EnvironmentData, summary="Reset simulation state")
async def reset_simulation(seed: Optional[int] = Query(None, description="Deterministic random seed")) -> EnvironmentData:
    """Reset the environmental simulation to initial baseline conditions."""
    return environment_service.reset(seed=seed)


_simulation_running = True


@router.get("/status", summary="Get simulation engine status")
async def get_simulation_status():
    """Return status of background simulation stepping."""
    env = environment_service.get_current_environment()
    return {
        "is_running": _simulation_running,
        "active_scenario": env.scenario_name,
        "mode": environment_service.provider.get_mode(),
        "timestamp": env.timestamp
    }


@router.post("/start", summary="Start or resume continuous simulation stepping")
async def start_simulation():
    """Resume automatic simulation clock."""
    global _simulation_running
    _simulation_running = True
    return {"status": "started", "is_running": True}


@router.post("/stop", summary="Pause continuous simulation stepping")
async def stop_simulation():
    """Pause automatic simulation clock."""
    global _simulation_running
    _simulation_running = False
    return {"status": "stopped", "is_running": False}
