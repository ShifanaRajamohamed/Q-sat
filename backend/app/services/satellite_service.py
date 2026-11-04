"""Satellite Service: Centralized manager for Satellite Digital Twin and Orbital Propagation."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Literal, Optional

from backend.app.config import settings
from backend.app.models.satellite import GroundStationConfig, SatelliteState
from digital_twin.satellite_model import SatelliteModel
from digital_twin.tle_orbital_provider import DOCUMENTED_REFERENCE_TLES, TLEOrbitalProvider

logger = logging.getLogger("qsat.satellite_service")


class SatelliteService:
    """Provides centralized access to satellite positional telemetry and tracking geometry."""

    def __init__(self):
        self._gs_config = GroundStationConfig(
            latitude=settings.GROUND_STATION_LAT,
            longitude=settings.GROUND_STATION_LON,
            altitude_m=settings.GROUND_STATION_ALT,
            min_elevation_deg=settings.MIN_ELEVATION
        )
        # Analytical reference pass model for controlled experiments
        self._reference_model = SatelliteModel(ground_station=self._gs_config)
        
        # SGP4 / Skyfield TLE orbital tracking provider
        self._active_tle_key = "MICIUS"
        self._tle_provider: Optional[TLEOrbitalProvider] = None
        try:
            self._tle_provider = TLEOrbitalProvider.from_reference_satellite(
                self._active_tle_key, ground_station=self._gs_config
            )
        except Exception as e:
            logger.warning("Could not initialize default TLE provider: %s", e)

        # Orbit mode: "reference_pass" (analytical) or "tle_prediction" (SGP4)
        self._orbit_mode: Literal["reference_pass", "tle_prediction"] = "reference_pass"
        self._sim_timestamp: float = 60.0
        self._base_utc: datetime = datetime(2024, 3, 1, 12, 0, 0, tzinfo=timezone.utc)

        logger.info(
            "SatelliteService initialized for ground station: %s. Active mode: %s",
            self._gs_config.name,
            self._orbit_mode
        )

    @property
    def model(self) -> SatelliteModel:
        return self._reference_model

    @property
    def orbit_mode(self) -> str:
        return self._orbit_mode

    def set_orbit_mode(self, mode: Literal["reference_pass", "tle_prediction"]) -> str:
        """Switch between reference pass mode and SGP4 TLE orbital tracking."""
        if mode not in ("reference_pass", "tle_prediction"):
            raise ValueError(f"Invalid orbit mode '{mode}'. Choose 'reference_pass' or 'tle_prediction'.")
        self._orbit_mode = mode
        logger.info("Orbital tracking mode switched to: %s", self._orbit_mode)
        return self._orbit_mode

    def get_state(self) -> SatelliteState:
        """Return current satellite topocentric state from active orbital provider."""
        if self._orbit_mode == "tle_prediction" and self._tle_provider is not None:
            return self._tle_provider.propagate(self._sim_timestamp, base_datetime=self._base_utc)
        return self._reference_model.get_state()

    def step(self, dt: float = 1.0) -> SatelliteState:
        """Propagate satellite state by dt seconds."""
        self._sim_timestamp += dt
        if self._orbit_mode == "tle_prediction" and self._tle_provider is not None:
            return self._tle_provider.propagate(self._sim_timestamp, base_datetime=self._base_utc)
        return self._reference_model.step(dt=dt)

    def reset(self, timestamp: float = 60.0) -> SatelliteState:
        """Reset satellite trajectory."""
        self._sim_timestamp = timestamp
        if self._orbit_mode == "tle_prediction" and self._tle_provider is not None:
            return self._tle_provider.propagate(self._sim_timestamp, base_datetime=self._base_utc)
        return self._reference_model.reset(timestamp=timestamp)

    def update_ground_station(self, config: GroundStationConfig) -> None:
        """Update active ground station parameters."""
        self._gs_config = config
        self._reference_model.update_ground_station(config)
        if self._tle_provider is not None:
            self._tle_provider = TLEOrbitalProvider.from_reference_satellite(
                self._active_tle_key, ground_station=self._gs_config
            )
        logger.info("Updated ground station: %s (Lat=%.4f, Lon=%.4f)", config.name, config.latitude, config.longitude)

    def get_ground_station(self) -> GroundStationConfig:
        """Return current ground station configuration."""
        return self._gs_config

    def list_reference_satellites(self) -> List[Dict[str, Any]]:
        """List documented reference satellites available for SGP4 tracking."""
        return [
            {
                "key": k,
                "satellite_name": v["satellite_name"],
                "norad_id": v["norad_id"],
                "epoch_iso": v["epoch_iso"],
                "retrieval_timestamp": v["retrieval_timestamp"],
                "source": v["source"],
                "description": v["description"],
                "assumed_payload": v["assumed_payload"]
            }
            for k, v in DOCUMENTED_REFERENCE_TLES.items()
        ]

    def select_tle_satellite(self, key: str) -> Dict[str, Any]:
        """Select active TLE reference satellite."""
        key_upper = key.upper()
        if key_upper not in DOCUMENTED_REFERENCE_TLES:
            raise KeyError(f"Unknown satellite key '{key}'. Available: {list(DOCUMENTED_REFERENCE_TLES.keys())}")
        self._active_tle_key = key_upper
        self._tle_provider = TLEOrbitalProvider.from_reference_satellite(
            self._active_tle_key, ground_station=self._gs_config
        )
        return {
            "status": "success",
            "active_satellite": DOCUMENTED_REFERENCE_TLES[key_upper]["satellite_name"],
            "epoch_iso": self._tle_provider.epoch_iso,
            "source": self._tle_provider.source
        }

    def predict_passes(self, hours: float = 24.0) -> List[Dict[str, Any]]:
        """Predict upcoming optical passes over the ground station."""
        if self._tle_provider is None:
            return []
        return self._tle_provider.predict_upcoming_passes(
            start_utc=self._base_utc,
            duration_hours=hours,
            step_seconds=30.0
        )


# Global singleton instance
satellite_service = SatelliteService()
