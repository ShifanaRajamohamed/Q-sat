"""SatelliteModel: High-level digital twin component for the satellite platform."""

from typing import Optional
from backend.app.config import settings
from backend.app.models.satellite import GroundStationConfig, SatelliteState
from digital_twin.orbital_model import OrbitalModel


class SatelliteModel:
    """Encapsulates the satellite digital twin state and pass propagation."""

    def __init__(
        self,
        ground_station: Optional[GroundStationConfig] = None,
        altitude_km: float = 500.0,
        satellite_name: str = "Q-SAT-LEO-1"
    ):
        if ground_station is None:
            ground_station = GroundStationConfig(
                latitude=settings.GROUND_STATION_LAT,
                longitude=settings.GROUND_STATION_LON,
                altitude_m=settings.GROUND_STATION_ALT,
                min_elevation_deg=settings.MIN_ELEVATION
            )
        self.ground_station = ground_station
        self.orbital_model = OrbitalModel(
            ground_station=self.ground_station,
            altitude_km=altitude_km,
            satellite_name=satellite_name
        )
        self.current_time = 60.0
        self.latest_state: SatelliteState = self.orbital_model.propagate(60.0)

    def step(self, dt: float = 1.0) -> SatelliteState:
        """Advance satellite along its orbit by dt seconds."""
        self.current_time += dt
        self.latest_state = self.orbital_model.propagate(self.current_time)
        return self.latest_state

    def reset(self, timestamp: float = 60.0) -> SatelliteState:
        """Reset satellite trajectory to initial pass conditions."""
        self.current_time = timestamp
        self.latest_state = self.orbital_model.propagate(self.current_time)
        return self.latest_state

    def get_state(self) -> SatelliteState:
        """Return the current satellite state vector."""
        return self.latest_state

    def update_ground_station(self, config: GroundStationConfig) -> None:
        """Update ground station geographic coordinates and tracking thresholds."""
        self.ground_station = config
        self.orbital_model.gs = config
        self.latest_state = self.orbital_model.propagate(self.current_time)
