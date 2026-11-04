"""Environment Service: Singleton manager for active EnvironmentProvider.

Coordinates between SimulationEnvironmentProvider, MQTTEnvironmentProvider,
and HistoricalWeatherProvider based on system configuration and user selection,
allowing dynamic scenario changes, historical weather replay, and telemetry queries.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Literal, Optional
from backend.app.config import settings
from backend.app.models.environment import (
    EnvironmentData,
    HistoricalReplayConfig,
    HistoricalReplayStatus,
    ScenarioInfo,
    ScenarioType,
)
from digital_twin.environment_provider import EnvironmentProvider
from digital_twin.historical_weather_provider import HistoricalWeatherProvider
from digital_twin.mqtt_environment_provider import MQTTEnvironmentProvider
from digital_twin.simulation_environment_provider import SimulationEnvironmentProvider
from simulation.scenarios.scenario_definitions import SCENARIO_CATALOG, SCENARIO_METADATA

logger = logging.getLogger("qsat.environment_service")


class EnvironmentService:
    """Singleton service managing environment telemetry, scenario controls, and historical replay."""

    def __init__(self):
        self._mode: str = settings.ENVIRONMENT_MODE
        self._historical_config = HistoricalReplayConfig()
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
        elif mode == "historical_replay":
            return HistoricalWeatherProvider(
                csv_path=self._historical_config.csv_file,
                start_datetime_iso=self._historical_config.start_datetime_iso,
                interpolation_mode=self._historical_config.interpolation_mode,
                assumed_turbulence=self._historical_config.assumed_turbulence,
                assumed_vibration_g=self._historical_config.assumed_vibration_g
            )
        else:
            return SimulationEnvironmentProvider(
                scenario=ScenarioType.CLEAR_SKY,
                seed=settings.RANDOM_SEED
            )

    @property
    def provider(self) -> EnvironmentProvider:
        return self._provider

    @property
    def mode(self) -> str:
        return self._mode

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
        """Switch simulation scenario (automatically switches to 'simulation' mode if currently in another mode)."""
        if self._mode != "simulation":
            self.set_mode("simulation")

        if isinstance(self._provider, SimulationEnvironmentProvider):
            self._provider.set_scenario(scenario, reseed=seed)
            return self._provider.step(dt=0.0)
        return self._provider.get_current_environment()

    def configure_historical_replay(self, config: HistoricalReplayConfig) -> HistoricalReplayStatus:
        """Switch to 'historical_replay' mode and initialize provider with target CSV and settings."""
        self._historical_config = config
        if isinstance(self._provider, MQTTEnvironmentProvider):
            self._provider.close()

        self._mode = "historical_replay"
        self._provider = HistoricalWeatherProvider(
            csv_path=config.csv_file,
            start_datetime_iso=config.start_datetime_iso,
            interpolation_mode=config.interpolation_mode,
            assumed_turbulence=config.assumed_turbulence,
            assumed_vibration_g=config.assumed_vibration_g
        )
        logger.info("Configured and switched to Historical Weather Replay: %s", config.csv_file)
        return self._provider.get_status()

    def get_historical_status(self) -> Optional[HistoricalReplayStatus]:
        """Return status if currently in historical replay mode."""
        if isinstance(self._provider, HistoricalWeatherProvider):
            return self._provider.get_status()
        return None

    def list_historical_files(self) -> List[Dict]:
        """List available historical weather CSV files with metadata."""
        weather_dir = Path("simulation/historical_weather")
        results = []
        if weather_dir.exists():
            for csv_file in weather_dir.glob("*.csv"):
                meta_file = csv_file.with_suffix(".meta.json")
                meta = {}
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                    except Exception:
                        pass
                results.append({
                    "filename": csv_file.name,
                    "filepath": str(csv_file).replace("\\", "/"),
                    "dataset_name": meta.get("dataset_name", csv_file.stem),
                    "provenance": meta.get("provenance", "LOCAL_CSV"),
                    "start_time_iso": meta.get("start_time_iso"),
                    "end_time_iso": meta.get("end_time_iso"),
                    "total_records": meta.get("total_records"),
                    "is_synthetic": meta.get("is_synthetic", False)
                })
        return results

    def get_available_scenarios(self) -> List[ScenarioInfo]:
        """Return catalog of available simulation scenarios."""
        return list(SCENARIO_METADATA.values())

    def get_scenario_info(self, scenario: ScenarioType) -> ScenarioInfo:
        """Return details for a specific scenario."""
        return SCENARIO_METADATA[scenario]

    def set_mode(self, mode: Literal["simulation", "mqtt", "historical_replay"]) -> None:
        """Dynamically toggle between 'simulation', 'mqtt', and 'historical_replay' modes."""
        if mode not in ["simulation", "mqtt", "historical_replay"]:
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
