"""Environment Service: Singleton manager for active EnvironmentProvider.

Coordinates between SimulationEnvironmentProvider and MQTTEnvironmentProvider
based on system configuration, allowing dynamic scenario changes and telemetry queries.
"""

import logging
from typing import Dict, List, Optional
from backend.app.config import settings
from backend.app.models.environment import EnvironmentData, ScenarioInfo, ScenarioType
from digital_twin.environment_provider import EnvironmentProvider
from digital_twin.mqtt_environment_provider import MQTTEnvironmentProvider
from digital_twin.simulation_environment_provider import SimulationEnvironmentProvider
from simulation.scenarios.scenario_definitions import SCENARIO_CATALOG, SCENARIO_METADATA

logger = logging.getLogger("qsat.environment_service")


class EnvironmentService:
    """Singleton service managing environment telemetry and scenario controls."""

    def __init__(self):
        self._mode = settings.ENVIRONMENT_MODE
        self._provider: EnvironmentProvider = self._create_provider(self._mode)
        logger.info("EnvironmentService initialized with mode: %s", self._mode)

    def _create_provider(self, mode: str) -> EnvironmentProvider:
        """Instantiate the appropriate provider implementation."""
        if mode == "mqtt":
            return MQTTEnvironmentProvider(
                broker_host=settings.MQTT_BROKER,
                broker_port=settings.MQTT_PORT,
                auto_fallback=True
            )
        else:
            return SimulationEnvironmentProvider(
                scenario=ScenarioType.CLEAR_SKY,
                seed=settings.RANDOM_SEED
            )

    @property
    def provider(self) -> EnvironmentProvider:
        return self._provider

    def get_current_environment(self) -> EnvironmentData:
        """Return latest environmental state vector."""
        return self._provider.get_current_environment()

    def step(self, dt: float = 1.0) -> EnvironmentData:
        """Step active provider forward by dt."""
        return self._provider.step(dt=dt)

    def reset(self, seed: Optional[int] = None) -> EnvironmentData:
        """Reset active provider state."""
        return self._provider.reset(seed=seed)

    def set_scenario(self, scenario: ScenarioType, seed: Optional[int] = None) -> EnvironmentData:
        """Switch simulation scenario."""
        if isinstance(self._provider, SimulationEnvironmentProvider):
            self._provider.set_scenario(scenario, reseed=seed)
            return self._provider.step(dt=0.0)
        elif isinstance(self._provider, MQTTEnvironmentProvider):
            # Also update fallback provider in MQTT mode
            self._provider.fallback_provider.set_scenario(scenario, reseed=seed)
            return self._provider.get_current_environment()
        return self._provider.get_current_environment()

    def get_available_scenarios(self) -> List[ScenarioInfo]:
        """Return catalog of available simulation scenarios."""
        return list(SCENARIO_METADATA.values())

    def get_scenario_info(self, scenario: ScenarioType) -> ScenarioInfo:
        """Return details for a specific scenario."""
        return SCENARIO_METADATA[scenario]

    def set_mode(self, mode: str) -> None:
        """Dynamically toggle between 'simulation' and 'mqtt' modes."""
        if mode not in ["simulation", "mqtt"]:
            raise ValueError(f"Invalid environment mode: {mode}")
        if mode != self._mode:
            # Clean up old provider if needed
            if isinstance(self._provider, MQTTEnvironmentProvider):
                self._provider.close()
            self._mode = mode
            self._provider = self._create_provider(mode)
            logger.info("Switched environment mode to: %s", mode)


# Global singleton instance
environment_service = EnvironmentService()
