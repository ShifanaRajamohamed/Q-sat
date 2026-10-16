"""QSATEnvironment: Gymnasium environment for satellite-to-ground quantum optical link control."""

from typing import Any, Dict, Optional, Tuple
import gymnasium as gym
from gymnasium import spaces
import numpy as np

from backend.app.config import settings
from backend.app.models.control import ControlAction
from backend.app.models.environment import EnvironmentData, ScenarioType
from backend.app.models.qkd import OpticalChannelState, QKDMetrics
from backend.app.models.satellite import SatelliteState
from digital_twin.optical_channel import OpticalChannelModel
from digital_twin.satellite_model import SatelliteModel
from digital_twin.simulation_environment_provider import SimulationEnvironmentProvider
from qkd.qkd_simulator import QKDSimulator
from ai.reward import RewardBreakdown, calculate_reward


class QSATEnvironment(gym.Env):
    """Reinforcement learning environment for continuous adaptive control of QKD ground stations."""

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        scenario: ScenarioType = ScenarioType.CLEAR_SKY,
        max_steps: int = 300,
        dt: float = 1.0,
        random_scenarios: bool = False,
        seed: Optional[int] = None
    ):
        super().__init__()
        self.scenario = scenario
        self.max_steps = max_steps
        self.dt = dt
        self.random_scenarios = random_scenarios
        self.initial_seed = seed if seed is not None else settings.RANDOM_SEED

        # Sub-systems
        self.env_provider = SimulationEnvironmentProvider(scenario=self.scenario, seed=self.initial_seed)
        self.satellite_model = SatelliteModel()
        self.optical_channel = OpticalChannelModel()
        self.qkd_simulator = QKDSimulator()

        # Action Space: Continuous control [-1.0, 1.0]^3 representing deltas
        # Action 0: Delta Transmission Power [-max_rate, +max_rate]
        # Action 1: Delta Photon Rate [-max_rate, +max_rate]
        # Action 2: Delta Beam Divergence [-max_rate, +max_rate]
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(3,), dtype=np.float32
        )

        # Observation Space: 15-dimensional normalized vector
        # [0] Satellite Elevation [0, 1]
        # [1] Slant Range [0, 1]
        # [2] Temperature [0, 1]
        # [3] Humidity [0, 1]
        # [4] Ambient Light [0, 1]
        # [5] Vibration [0, 1]
        # [6] Cloud Factor [0, 1]
        # [7] Turbulence Index [0, 1]
        # [8] Channel Path Loss [0, 1]
        # [9] QBER [0, 1]
        # [10] Normalized Secret Key Rate [0, 1]
        # [11] Normalized Received Photon Rate [0, 1]
        # [12] Current Transmission Power [0, 1]
        # [13] Current Photon Rate [0, 1]
        # [14] Current Beam Divergence [0, 1]
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(15,), dtype=np.float32
        )

        # Actuator State
        self.power_pct: float = 50.0
        self.photon_rate_norm: float = 0.70
        self.beam_divergence_norm: float = 0.25

        self.current_step: int = 0
        self.current_time: float = 0.0

        # Latest cache
        self.latest_sat: Optional[SatelliteState] = None
        self.latest_env: Optional[EnvironmentData] = None
        self.latest_channel: Optional[OpticalChannelState] = None
        self.latest_qkd: Optional[QKDMetrics] = None
        self.latest_reward: Optional[RewardBreakdown] = None

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reset environment to initial episode state."""
        super().reset(seed=seed)
        eff_seed = seed if seed is not None else self.initial_seed

        if self.random_scenarios:
            scenarios = list(ScenarioType)
            chosen_scenario = scenarios[self.np_random.integers(0, len(scenarios))]
            self.env_provider.set_scenario(chosen_scenario, reseed=eff_seed)
        else:
            self.env_provider.set_scenario(self.scenario, reseed=eff_seed)

        self.current_step = 0
        self.current_time = 0.0

        self.latest_env = self.env_provider.reset(seed=eff_seed)
        self.latest_sat = self.satellite_model.reset(60.0)

        # Baseline actuators
        self.power_pct = 50.0
        self.photon_rate_norm = 0.70
        self.beam_divergence_norm = 0.25

        self.latest_channel = self.optical_channel.calculate_link_state(
            satellite=self.latest_sat,
            environment=self.latest_env,
            transmission_power_pct=self.power_pct,
            photon_rate_norm=self.photon_rate_norm,
            beam_divergence_norm=self.beam_divergence_norm
        )
        self.latest_qkd = self.qkd_simulator.step(
            channel_state=self.latest_channel,
            environment=self.latest_env,
            timestamp=self.current_time
        )

        obs = self._build_observation()
        info = {
            "scenario": self.env_provider.scenario.value,
            "qber": self.latest_qkd.qber,
            "skr": self.latest_qkd.secret_key_rate,
            "elevation": self.latest_sat.elevation_deg
        }
        return obs, info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """Execute one continuous control step."""
        action = np.clip(action, -1.0, 1.0)
        rate_limit = settings.MAX_RATE_OF_CHANGE  # 0.20

        # Map actions to actuator parameter deltas
        delta_p = float(action[0] * (rate_limit * 100.0))  # Power delta [-20%, +20%]
        delta_r = float(action[1] * rate_limit)            # Photon rate delta [-0.20, +0.20]
        delta_d = float(action[2] * rate_limit)            # Divergence delta [-0.20, +0.20]

        # Apply deltas with hardware physical clamps
        self.power_pct = float(np.clip(
            self.power_pct + delta_p,
            settings.MIN_TRANSMISSION_POWER, settings.MAX_TRANSMISSION_POWER
        ))
        self.photon_rate_norm = float(np.clip(
            self.photon_rate_norm + delta_r,
            settings.MIN_PHOTON_RATE, settings.MAX_PHOTON_RATE
        ))
        self.beam_divergence_norm = float(np.clip(
            self.beam_divergence_norm + delta_d,
            settings.MIN_BEAM_DIVERGENCE, settings.MAX_BEAM_DIVERGENCE
        ))

        # Advance digital twin physics
        self.current_step += 1
        self.current_time += self.dt

        self.latest_sat = self.satellite_model.step(dt=self.dt)
        self.latest_env = self.env_provider.step(dt=self.dt)
        self.latest_channel = self.optical_channel.calculate_link_state(
            satellite=self.latest_sat,
            environment=self.latest_env,
            transmission_power_pct=self.power_pct,
            photon_rate_norm=self.photon_rate_norm,
            beam_divergence_norm=self.beam_divergence_norm
        )
        self.latest_qkd = self.qkd_simulator.step(
            channel_state=self.latest_channel,
            environment=self.latest_env,
            timestamp=self.current_time
        )

        # Compute normalized multi-objective reward
        self.latest_reward = calculate_reward(
            secret_key_rate=self.latest_qkd.secret_key_rate,
            qber=self.latest_qkd.qber,
            transmission_power_pct=self.power_pct,
            delta_power=delta_p,
            delta_photon_rate=delta_r,
            delta_divergence=delta_d,
            is_link_visible=self.latest_sat.is_visible
        )

        obs = self._build_observation()
        reward = self.latest_reward.total_reward
        terminated = self.current_step >= self.max_steps
        truncated = False

        info = {
            "qber": self.latest_qkd.qber,
            "skr": self.latest_qkd.secret_key_rate,
            "channel_loss_db": self.latest_channel.total_loss_db,
            "power_pct": self.power_pct,
            "reward_breakdown": self.latest_reward.__dict__,
            "is_visible": self.latest_sat.is_visible
        }
        return obs, reward, terminated, truncated, info

    def _build_observation(self) -> np.ndarray:
        """Construct normalized 15-dimensional observation array."""
        elev_norm = max(0.0, min(1.0, (self.latest_sat.elevation_deg + 10.0) / 100.0))
        range_norm = max(0.0, min(1.0, self.latest_sat.slant_range_km / 2000.0))
        temp_norm = max(0.0, min(1.0, (self.latest_env.temperature + 20.0) / 70.0))
        hum_norm = self.latest_env.humidity / 100.0
        light_norm = max(0.0, min(1.0, self.latest_env.ambient_light / 100000.0))
        vib_norm = max(0.0, min(1.0, self.latest_env.vibration / 2.0))
        cloud_norm = self.latest_env.cloud_factor
        turb_norm = self.latest_env.turbulence
        loss_norm = max(0.0, min(1.0, self.latest_channel.total_loss_db / 60.0))
        qber_norm = max(0.0, min(1.0, self.latest_qkd.qber / 0.50))
        skr_norm = max(0.0, min(1.0, self.latest_qkd.secret_key_rate / 30000.0))
        rx_norm = max(0.0, min(1.0, self.latest_channel.received_photon_rate / 500000.0))
        pwr_norm = self.power_pct / 100.0
        rate_norm = self.photon_rate_norm
        div_norm = self.beam_divergence_norm

        obs = np.array([
            elev_norm, range_norm, temp_norm, hum_norm, light_norm,
            vib_norm, cloud_norm, turb_norm, loss_norm, qber_norm,
            skr_norm, rx_norm, pwr_norm, rate_norm, div_norm
        ], dtype=np.float32)
        return obs

    def render(self):
        """Print human-readable telemetry frame."""
        print(
            f"Step {self.current_step} | Elev: {self.latest_sat.elevation_deg:.1f}° | "
            f"QBER: {self.latest_qkd.qber*100:.2f}% | SKR: {self.latest_qkd.secret_key_rate/1000:.2f} kbps | "
            f"Power: {self.power_pct:.1f}% | Div: {self.beam_divergence_norm:.2f}"
        )
