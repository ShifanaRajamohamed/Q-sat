"""Pydantic models for Satellite telemetry, orbital geometry, and Ground Station configuration."""

from typing import Literal, Optional
from pydantic import BaseModel, Field
from backend.app.config import settings


class GroundStationConfig(BaseModel):
    """Ground station geographic coordinates and tracking thresholds."""
    name: str = Field(default_factory=lambda: settings.GROUND_STATION_NAME, description="Ground Station identifier")
    latitude: float = Field(default_factory=lambda: settings.GROUND_STATION_LAT, description="Latitude in degrees North [-90, 90]")
    longitude: float = Field(default_factory=lambda: settings.GROUND_STATION_LON, description="Longitude in degrees East [-180, 180]")
    altitude_m: float = Field(default_factory=lambda: settings.GROUND_STATION_ALT, ge=0.0, description="Altitude above mean sea level in meters")
    min_elevation_deg: float = Field(default_factory=lambda: settings.MIN_ELEVATION, ge=0.0, le=45.0, description="Minimum elevation cutoff angle (degrees)")


class SatelliteState(BaseModel):
    """Comprehensive satellite positional and topocentric geometric state vector."""
    timestamp: float = Field(..., description="Simulation epoch timestamp in seconds")
    satellite_name: str = Field("Q-SAT-LEO-1", description="Satellite identifier")
    altitude_km: float = Field(..., ge=100.0, le=2000.0, description="Orbital altitude above Earth surface in km")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Sub-satellite geographic latitude in degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Sub-satellite geographic longitude in degrees")
    azimuth_deg: float = Field(..., ge=0.0, le=360.0, description="Topocentric azimuth angle from ground station (0=N, 90=E)")
    elevation_deg: float = Field(..., ge=-90.0, le=90.0, description="Topocentric elevation angle above local horizon (degrees)")
    slant_range_km: float = Field(..., ge=0.0, description="Euclidean distance from ground station to satellite in km")
    orbital_velocity_km_s: float = Field(..., ge=5.0, le=10.0, description="Orbital speed in km/s")
    is_visible: bool = Field(..., description="True if elevation >= min_elevation threshold")
    pass_progress: float = Field(0.0, ge=0.0, le=1.0, description="Normalized progress through current pass [0.0 to 1.0]")
    link_status: Literal["ACQUIRED", "TRACKING", "UNAVAILABLE"] = Field(
        "UNAVAILABLE", description="Optical line-of-sight tracking link status"
    )
    pass_id: int = Field(1, description="Sequential pass identifier")
    time_to_los_s: Optional[float] = Field(None, description="Estimated seconds until Loss of Signal (below threshold)")
    time_to_aos_s: Optional[float] = Field(None, description="Estimated seconds until Acquisition of Signal (above threshold)")
    
    # Provenance and tracking metadata
    is_orbital_prediction: bool = Field(False, description="True indicates calculated prediction from orbital propagator, NOT direct satellite telemetry")
    orbital_source: str = Field("ANALYTICAL_REFERENCE", description="Source of orbital propagation (ANALYTICAL_REFERENCE, SGP4_TLE_PREDICTION)")
    orbital_epoch: Optional[str] = Field(None, description="Orbital element epoch in ISO 8601 UTC")
    retrieval_timestamp: Optional[str] = Field(None, description="Timestamp when orbital elements were retrieved")
    epoch_age_days: Optional[float] = Field(None, description="Age of orbital elements in days relative to current propagation time")
    epoch_warning: Optional[str] = Field(None, description="Warning if propagation is far from orbital epoch")
    assumed_payload_parameters: Optional[dict] = Field(None, description="Configured optical payload assumptions (not measured telemetry)")
