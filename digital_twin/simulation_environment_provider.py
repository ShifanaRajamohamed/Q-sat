"""SimulationEnvironmentProvider: Synthetic environmental time-series generator.

Implements the EnvironmentProvider interface using a vectorized Ornstein-Uhlenbeck
mean-reverting stochastic process. Supports Scenarios A through F with deterministic
reproducibility via configurable random seeds.
"""

from typing import Optional
import numpy as np
import pandas as pd

from backend.app.config import settings
from backend.app.models.environment import EnvironmentData, ScenarioType
from digital_twin.environment_provider import EnvironmentProvider
from simulation.scenarios.scenario_definitions import SCENARIO_CATALOG, ScenarioParams


class SimulationEnvironmentProvider(EnvironmentProvider):
    """Generates synthetic environmental telemetry with physically plausible stochastic dynamics."""

    def __init__(self, scenario: ScenarioType = ScenarioType.CLEAR_SKY, seed: Optional[int] = None, use_dataset: bool = True):
        self.scenario = scenario
        self.seed = seed if seed is not None else settings.RANDOM_SEED
        self.rng = np.random.RandomState(self.seed)
        self.use_dataset = use_dataset
        self.dataset_df: Optional[pd.DataFrame] = None
        self.dataset_idx: int = 0

        self.current_time = 0.0
        self.params: ScenarioParams = SCENARIO_CATALOG[self.scenario]

        # State vector initialized to scenario means
        self.temperature = self.params.temp_mean
        self.humidity = self.params.humidity_mean
        self.ambient_light = self.params.ambient_light_mean
        self.vibration = self.params.vibration_mean
        self.cloud_factor = self.params.cloud_mean
        self.turbulence = self.params.turbulence_mean

        self.reset(seed=self.seed)

    def _try_load_dataset(self) -> Optional[pd.DataFrame]:
        """Attempt to load pre-generated empirical dataset from simulation/generated_data/."""
        if not self.use_dataset:
            return None
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        # Only load pre-generated dataset if it specifically matches this seed
        csv_file = root / "simulation" / "generated_data" / f"{self.scenario.value.lower()}_seed{self.seed}.csv"
        if csv_file.exists():
            try:
                df = pd.read_csv(csv_file)
                required = ["temperature", "humidity", "ambient_light", "vibration", "cloud_factor", "turbulence"]
                if all(c in df.columns for c in required) and len(df) > 0:
                    return df
            except Exception:
                pass
        return None

    def reset(self, seed: Optional[int] = None) -> EnvironmentData:
        """Reset the stochastic generator and reinitialize state around scenario baseline."""
        if seed is not None:
            self.seed = seed
        self.rng = np.random.RandomState(self.seed)
        self.params = SCENARIO_CATALOG[self.scenario]
        self.current_time = 0.0
        self.dataset_df = self._try_load_dataset()
        self.dataset_idx = 0

        if self.dataset_df is not None and not self.dataset_df.empty:
            row = self.dataset_df.iloc[0]
            self.temperature = float(row["temperature"])
            self.humidity = float(row["humidity"])
            self.ambient_light = float(row["ambient_light"])
            self.vibration = float(row["vibration"])
            self.cloud_factor = float(row["cloud_factor"])
            self.turbulence = float(row["turbulence"])
        else:
            # Initialize with slight initial stochastic perturbation
            self.temperature = float(np.clip(
                self.params.temp_mean + self.rng.normal(0, self.params.temp_sigma * 0.5),
                self.params.temp_min, self.params.temp_max
            ))
            self.humidity = float(np.clip(
                self.params.humidity_mean + self.rng.normal(0, self.params.humidity_sigma * 0.5),
                self.params.humidity_min, self.params.humidity_max
            ))
            self.ambient_light = float(np.clip(
                self.params.ambient_light_mean + self.rng.normal(0, self.params.ambient_light_sigma * 0.5),
                self.params.ambient_light_min, self.params.ambient_light_max
            ))
            self.vibration = float(np.clip(
                self.params.vibration_mean + self.rng.normal(0, self.params.vibration_sigma * 0.5),
                self.params.vibration_min, self.params.vibration_max
            ))
            self.cloud_factor = float(np.clip(
                self.params.cloud_mean + self.rng.normal(0, self.params.cloud_sigma * 0.5),
                self.params.cloud_min, self.params.cloud_max
            ))
            self.turbulence = float(np.clip(
                self.params.turbulence_mean + self.rng.normal(0, self.params.turbulence_sigma * 0.5),
                self.params.turbulence_min, self.params.turbulence_max
            ))

        return self.get_current_environment()

    def set_scenario(self, scenario: ScenarioType, reseed: Optional[int] = None) -> None:
        """Dynamically switch active scenario profile."""
        if scenario not in SCENARIO_CATALOG:
            raise ValueError(f"Unknown scenario: {scenario}")
        self.scenario = scenario
        self.params = SCENARIO_CATALOG[self.scenario]
        if reseed is not None:
            self.seed = reseed
            self.rng = np.random.RandomState(self.seed)
        self.dataset_df = self._try_load_dataset()
        self.dataset_idx = 0

    def step(self, dt: float = 1.0) -> EnvironmentData:
        """Advance environmental physics by dt seconds using empirical dataset replay or OU SDE."""
        if self.dataset_df is not None and not self.dataset_df.empty:
            if dt > 0:
                self.dataset_idx = (self.dataset_idx + 1) % len(self.dataset_df)
                row = self.dataset_df.iloc[self.dataset_idx]
                self.temperature = float(row["temperature"])
                self.humidity = float(row["humidity"])
                self.ambient_light = float(row["ambient_light"])
                self.vibration = float(row["vibration"])
                self.cloud_factor = float(row["cloud_factor"])
                self.turbulence = float(row["turbulence"])
                self.current_time += dt
            return self.get_current_environment()

        p = self.params
        sqrt_dt = np.sqrt(dt)

        # 1. Temperature evolution
        d_temp = p.temp_theta * (p.temp_mean - self.temperature) * dt + p.temp_sigma * sqrt_dt * self.rng.normal(0, 1)
        self.temperature = float(np.clip(self.temperature + d_temp, p.temp_min, p.temp_max))

        # 2. Relative Humidity evolution
        d_hum = p.humidity_theta * (p.humidity_mean - self.humidity) * dt + p.humidity_sigma * sqrt_dt * self.rng.normal(0, 1)
        self.humidity = float(np.clip(self.humidity + d_hum, p.humidity_min, p.humidity_max))

        # 3. Ambient Optical Noise evolution
        d_lux = p.ambient_light_theta * (p.ambient_light_mean - self.ambient_light) * dt + p.ambient_light_sigma * sqrt_dt * self.rng.normal(0, 1)
        self.ambient_light = float(np.clip(self.ambient_light + d_lux, p.ambient_light_min, p.ambient_light_max))

        # 4. Platform Vibration evolution
        d_vib = p.vibration_theta * (p.vibration_mean - self.vibration) * dt + p.vibration_sigma * sqrt_dt * self.rng.normal(0, 1)
        self.vibration = float(np.clip(self.vibration + d_vib, p.vibration_min, p.vibration_max))

        # 5. Cloud Factor evolution
        d_cloud = p.cloud_theta * (p.cloud_mean - self.cloud_factor) * dt + p.cloud_sigma * sqrt_dt * self.rng.normal(0, 1)
        self.cloud_factor = float(np.clip(self.cloud_factor + d_cloud, p.cloud_min, p.cloud_max))

        # 6. Turbulence evolution
        d_turb = p.turbulence_theta * (p.turbulence_mean - self.turbulence) * dt + p.turbulence_sigma * sqrt_dt * self.rng.normal(0, 1)
        self.turbulence = float(np.clip(self.turbulence + d_turb, p.turbulence_min, p.turbulence_max))

        self.current_time += dt
        return self.get_current_environment()

    def get_current_environment(self) -> EnvironmentData:
        """Return the current immutable snapshot of environmental telemetry."""
        return EnvironmentData(
            timestamp=round(self.current_time, 3),
            temperature=round(self.temperature, 2),
            humidity=round(self.humidity, 2),
            ambient_light=round(self.ambient_light, 1),
            vibration=round(self.vibration, 4),
            cloud_factor=round(self.cloud_factor, 4),
            turbulence=round(self.turbulence, 4),
            data_source="SIMULATION",
            scenario_name=self.scenario.value
        )

    def generate_time_series(self, duration_seconds: float = 300.0, dt: float = 1.0) -> pd.DataFrame:
        """Generate a complete reproducible time-series trace for analysis or export."""
        records = []
        steps = int(duration_seconds / dt)
        self.reset(seed=self.seed)

        for _ in range(steps):
            data = self.step(dt=dt)
            records.append(data.model_dump())

        return pd.DataFrame(records)

    def get_mode(self) -> str:
        return "simulation"

    def is_healthy(self) -> bool:
        return True
