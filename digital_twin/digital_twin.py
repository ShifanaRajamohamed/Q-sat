"""DigitalTwin: Integrated digital twin orchestrator for Satellite, Environment, and Optical Link."""

from typing import Optional
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState
from backend.app.models.satellite import GroundStationConfig, SatelliteState
from digital_twin.environment_provider import EnvironmentProvider
from digital_twin.optical_channel import OpticalChannelModel
from digital_twin.satellite_model import SatelliteModel


class DigitalTwin:
    """Combines Satellite orbital mechanics, environmental telemetry, and optical channel physics."""

    def __init__(
        self,
        environment_provider: EnvironmentProvider,
        ground_station: Optional[GroundStationConfig] = None,
        satellite_altitude_km: float = 500.0
    ):
        self.env_provider = environment_provider
        self.satellite_model = SatelliteModel(
            ground_station=ground_station,
            altitude_km=satellite_altitude_km
        )
        self.optical_channel = OpticalChannelModel()

        self.current_time = 0.0

        # Latest states
        self.latest_satellite: SatelliteState = self.satellite_model.get_state()
        self.latest_environment: EnvironmentData = self.env_provider.get_current_environment()
        self.latest_channel: OpticalChannelState = self.optical_channel.calculate_link_state(
            satellite=self.latest_satellite,
            environment=self.latest_environment
        )

    def step(
        self,
        dt: float = 1.0,
        transmission_power_pct: float = 100.0,
        photon_rate_norm: float = 1.0,
        beam_divergence_norm: float = 0.20
    ) -> tuple[SatelliteState, EnvironmentData, OpticalChannelState]:
        """Advance time step across satellite motion, environmental dynamics, and optical link."""
        self.current_time += dt
        self.latest_satellite = self.satellite_model.step(dt=dt)
        self.latest_environment = self.env_provider.step(dt=dt)
        self.latest_channel = self.optical_channel.calculate_link_state(
            satellite=self.latest_satellite,
            environment=self.latest_environment,
            transmission_power_pct=transmission_power_pct,
            photon_rate_norm=photon_rate_norm,
            beam_divergence_norm=beam_divergence_norm
        )
        return self.latest_satellite, self.latest_environment, self.latest_channel

    def reset(self, seed: Optional[int] = None) -> tuple[SatelliteState, EnvironmentData, OpticalChannelState]:
        """Reset digital twin state to initial pass conditions."""
        self.current_time = 0.0
        self.latest_satellite = self.satellite_model.reset(0.0)
        self.latest_environment = self.env_provider.reset(seed=seed)
        self.latest_channel = self.optical_channel.calculate_link_state(
            satellite=self.latest_satellite,
            environment=self.latest_environment
        )
        return self.latest_satellite, self.latest_environment, self.latest_channel
