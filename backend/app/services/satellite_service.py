"""Satellite Service: Singleton manager for Satellite Digital Twin state."""

import logging
from typing import Optional
from backend.app.config import settings
from backend.app.models.satellite import GroundStationConfig, SatelliteState
from digital_twin.satellite_model import SatelliteModel

logger = logging.getLogger("qsat.satellite_service")


class SatelliteService:
    """Provides centralized access to satellite positional telemetry and tracking geometry."""

    def __init__(self):
        gs_config = GroundStationConfig(
            latitude=settings.GROUND_STATION_LAT,
            longitude=settings.GROUND_STATION_LON,
            altitude_m=settings.GROUND_STATION_ALT,
            min_elevation_deg=settings.MIN_ELEVATION
        )
        self._model = SatelliteModel(ground_station=gs_config)
        logger.info("SatelliteService initialized for ground station: %s", gs_config.name)

    @property
    def model(self) -> SatelliteModel:
        return self._model

    def get_state(self) -> SatelliteState:
        """Return current satellite topocentric state."""
        return self._model.get_state()

    def step(self, dt: float = 1.0) -> SatelliteState:
        """Propagate satellite state by dt seconds."""
        return self._model.step(dt=dt)

    def reset(self, timestamp: float = 0.0) -> SatelliteState:
        """Reset satellite trajectory."""
        return self._model.reset(timestamp=timestamp)

    def update_ground_station(self, config: GroundStationConfig) -> None:
        """Update active ground station parameters."""
        self._model.update_ground_station(config)
        logger.info("Updated ground station: Lat=%.4f, Lon=%.4f", config.latitude, config.longitude)

    def get_ground_station(self) -> GroundStationConfig:
        """Return current ground station configuration."""
        return self._model.ground_station


# Global singleton instance
satellite_service = SatelliteService()
