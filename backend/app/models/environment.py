"""Pydantic data models for environmental telemetry, scenario management, and historical replay."""

from enum import Enum
from typing import Dict, List, Literal, Optional, Tuple
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
    
    Adheres to Scientific Labeling rules (SIMULATION vs HARDWARE vs HISTORICAL_REPLAY).
    Separates meteorological cloud cover from optical cloud extinction factor.
    Explicitly tracks provenance of measured, reanalyzed, and assumed fields.
    """
    timestamp: float = Field(..., description="Simulation epoch timestamp in seconds")
    temperature: float = Field(..., ge=-40.0, le=70.0, description="Ambient temperature in degrees Celsius (°C)")
    humidity: float = Field(..., ge=0.0, le=100.0, description="Relative humidity percentage (%)")
    ambient_light: float = Field(..., ge=0.0, description="Ambient optical noise intensity (lux)")
    vibration: float = Field(..., ge=0.0, description="Ground station platform vibration acceleration (g)")
    cloud_factor: float = Field(..., ge=0.0, le=1.0, description="Effective optical cloud extinction factor [0.0 = clear, 1.0 = overcast]")
    turbulence: float = Field(..., ge=0.0, le=1.0, description="Atmospheric turbulence index [0.0 = calm, 1.0 = severe]")
    data_source: Literal["SIMULATION", "HARDWARE", "HISTORICAL_REPLAY"] = Field("SIMULATION", description="Provenance of telemetry data")
    scenario_name: Optional[str] = Field(None, description="Active simulation scenario name if simulated")

    # Historical Weather Replay & Physical Extensions
    meteorological_cloud_cover_pct: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Meteorological total cloud cover percentage (distinct from optical cloud_factor)"
    )
    wind_speed_m_s: Optional[float] = Field(
        None, ge=0.0, description="Surface wind speed at 10m height in meters per second (m/s)"
    )
    datetime_iso: Optional[str] = Field(
        None, description="Calendar timestamp during historical replay (ISO 8601 string)"
    )
    is_interpolated: bool = Field(
        False, description="True if value was temporally interpolated rather than an exact observation"
    )
    interpolation_method: Optional[Literal["HOLD", "LINEAR"]] = Field(
        None, description="Temporal reconstruction method applied ('HOLD' or 'LINEAR')"
    )
    field_provenance: Optional[Dict[str, str]] = Field(
        None, description="Per-field metadata indicating 'MEASURED', 'REANALYSIS', 'DERIVED_OPTICAL', or 'CONFIGURED_ASSUMPTION'"
    )


class ScenarioInfo(BaseModel):
    """Metadata describing a benchmark simulation scenario."""
    id: ScenarioType
    name: str
    description: str
    expected_cloud_range: Tuple[float, float]
    expected_turbulence_range: Tuple[float, float]
    expected_humidity_range: Tuple[float, float]
    expected_vibration_range: Tuple[float, float]
    expected_ambient_light_range: Tuple[float, float]


class SetScenarioRequest(BaseModel):
    """Request payload for switching simulation scenario."""
    scenario: ScenarioType
    seed: Optional[int] = Field(None, description="Optional seed for deterministic reset")


class SimulationStepRequest(BaseModel):
    """Request payload for manually advancing the simulation."""
    dt: float = Field(1.0, ge=0.01, le=60.0, description="Time step duration in seconds")


class HistoricalReplayConfig(BaseModel):
    """Configuration options for initializing Historical Weather Replay."""
    csv_file: str = Field(
        "simulation/historical_weather/tiruchirappalli_20240301_20240331_era5.csv",
        description="Path to timestamped historical weather CSV"
    )
    start_datetime_iso: Optional[str] = Field(
        None, description="Target start date/time (e.g. '2024-03-01T00:00:00Z'). Defaults to start of file."
    )
    interpolation_mode: Literal["HOLD", "LINEAR"] = Field(
        "LINEAR", description="Reconstruction mode: 'HOLD' (Zero-order hold) or 'LINEAR' (interpolated)"
    )
    assumed_turbulence: float = Field(
        0.12, ge=0.01, le=1.0, description="Configured turbulence assumption for unmeasured atmospheric scintillation"
    )
    assumed_vibration_g: float = Field(
        0.015, ge=0.001, le=1.0, description="Configured mechanical mount vibration assumption (g)"
    )


class HistoricalReplayStatus(BaseModel):
    """Status details for active historical weather replay."""
    is_active: bool
    csv_file: str
    dataset_source: str
    location_name: str
    latitude: float
    longitude: float
    file_start_iso: Optional[str]
    file_end_iso: Optional[str]
    current_time_iso: Optional[str]
    total_records: int
    interpolation_mode: str
    is_interpolated: bool
    notes: str
