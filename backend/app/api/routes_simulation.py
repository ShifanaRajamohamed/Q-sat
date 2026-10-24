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


@router.get("/datasets", summary="List all empirical scenario datasets and summary stats")
async def list_simulation_datasets():
    """Retrieve catalog of all pre-generated empirical CSV datasets."""
    from pathlib import Path
    import pandas as pd
    root = Path(__file__).resolve().parent.parent.parent.parent
    data_dir = root / "simulation" / "generated_data"
    catalog = []
    if data_dir.exists():
        for csv_file in sorted(data_dir.glob("*.csv")):
            try:
                df = pd.read_csv(csv_file)
                stats = {}
                numeric_cols = ["temperature", "humidity", "ambient_light", "vibration", "cloud_factor", "turbulence"]
                for col in numeric_cols:
                    if col in df.columns:
                        stats[col] = {
                            "mean": round(float(df[col].mean()), 3),
                            "std": round(float(df[col].std()), 3),
                            "min": round(float(df[col].min()), 3),
                            "max": round(float(df[col].max()), 3),
                        }
                scenario_name = csv_file.stem.split("_seed")[0].upper()
                catalog.append({
                    "filename": csv_file.name,
                    "scenario": scenario_name,
                    "row_count": len(df),
                    "summary": stats,
                    "sample_rows": df.head(5).to_dict(orient="records")
                })
            except Exception:
                continue
    return {
        "status": "success",
        "provenance": "100% SOFTWARE DIGITAL TWIN & DATASET",
        "total_datasets": len(catalog),
        "datasets": catalog
    }


@router.get("/dataset/{scenario}", summary="Get full rows of a specific scenario dataset")
async def get_simulation_dataset(scenario: str):
    """Retrieve all empirical time-series samples for a given scenario dataset."""
    from pathlib import Path
    import pandas as pd
    root = Path(__file__).resolve().parent.parent.parent.parent
    data_dir = root / "simulation" / "generated_data"
    filename = f"{scenario.lower()}_seed42.csv"
    csv_file = data_dir / filename
    if not csv_file.exists():
        # Try matching any seed file for this scenario
        matches = list(data_dir.glob(f"{scenario.lower()}_seed*.csv"))
        if matches:
            csv_file = matches[0]
        else:
            return {"status": "error", "message": f"Dataset for scenario {scenario} not found"}

    df = pd.read_csv(csv_file)
    return {
        "status": "success",
        "scenario": scenario.upper(),
        "filename": csv_file.name,
        "total_samples": len(df),
        "records": df.to_dict(orient="records")
    }

