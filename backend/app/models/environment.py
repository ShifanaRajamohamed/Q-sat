"""Pydantic data models for environmental telemetry and scenario management."""

from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ScenarioType(str, Enum):
    CLEAR_SKY = "CLEAR_SKY"                      # Scenario A: Low cloud, low turbulence, low ambient noise
    HUMID = "HUMID"                              # Scenario B: High humidity, moderate atmospheric attenuation
    CLOUDY = "CLOUDY"                            # Scenario C: High cloud factor, heavy optical extinction
    HIGH_AMBIENT_LIGHT = "HIGH_AMBIENT_LIGHT"    # Scenario D: Direct sun/daytime background optical noise
    VIBRATION = "VIBRATION"                      # Scenario E: High mechanical/platform jitter, pointing error
    COMBINED_DEGRADATION = "COMBINED_DEGRADATION"# Scenario F: Humidity + turbulence + cloud + vibration


class EnvironmentData(BaseModel):
    """Environmental state vector at time step t.
    
    Adheres to Scientific Labeling rules (SIMULATION vs HARDWARE).
    """
    timestamp: float = Field(..., description="Simulation epoch timestamp in seconds")
    temperature: float = Field(..., ge=-40.0, le=70.0, description="Ambient temperature in degrees Celsius (°C)")
    humidity: float = Field(..., ge=0.0, le=100.0, description="Relative humidity percentage (%)")
    ambient_light: float = Field(..., ge=0.0, description="Ambient optical noise intensity (lux)")
    vibration: float = Field(..., ge=0.0, description="Ground station platform vibration acceleration (g)")
    cloud_factor: float = Field(..., ge=0.0, le=1.0, description="Cloud obscuration factor [0.0 = clear, 1.0 = overcast]")
    turbulence: float = Field(..., ge=0.0, le=1.0, description="Atmospheric turbulence index [0.0 = calm, 1.0 = severe]")
    data_source: Literal["SIMULATION", "HARDWARE"] = Field("SIMULATION", description="Provenance of telemetry data")
    scenario_name: Optional[str] = Field(None, description="Active simulation scenario name if simulated")


class ScenarioInfo(BaseModel):
    """Metadata describing a benchmark simulation scenario."""
    id: ScenarioType
    name: str
    description: str
    expected_cloud_range: tuple[float, float]
    expected_turbulence_range: tuple[float, float]
    expected_humidity_range: tuple[float, float]
    expected_vibration_range: tuple[float, float]
    expected_ambient_light_range: tuple[float, float]


class SetScenarioRequest(BaseModel):
    """Request payload for switching simulation scenario."""
    scenario: ScenarioType
    seed: Optional[int] = Field(None, description="Optional seed for deterministic reset")


class SimulationStepRequest(BaseModel):
    """Request payload for manually advancing the simulation."""
    dt: float = Field(1.0, ge=0.01, le=60.0, description="Time step duration in seconds")
