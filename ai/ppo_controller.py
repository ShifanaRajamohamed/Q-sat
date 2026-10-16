"""PPOController: Deep Reinforcement Learning continuous controller using Proximal Policy Optimization."""

import logging
from pathlib import Path
from typing import Optional
import numpy as np

from backend.app.config import settings
from backend.app.models.control import ControlAction
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState, QKDMetrics
from backend.app.models.satellite import SatelliteState
from ai.rule_based_controller import RuleBasedController

logger = logging.getLogger("qsat.ppo_controller")


class PPOController:
    """Uses a trained PPO neural policy (or heuristic fallback if untrained) to output continuous actions."""

    def __init__(self, model_path: Optional[str] = "models/ppo_qsat.zip"):
        self.model_path = Path(model_path) if model_path else None
        self.model = None
        self.fallback_controller = RuleBasedController()

        # Actuator State
        self.power_pct: float = 50.0
        self.photon_rate_norm: float = 0.70
        self.beam_divergence_norm: float = 0.25
        self.rate_limit = settings.MAX_RATE_OF_CHANGE

        self._load_model_if_available()

    def _load_model_if_available(self) -> bool:
        """Attempt loading trained Stable-Baselines3 PPO model."""
        if self.model_path and self.model_path.exists():
            try:
                from stable_baselines3 import PPO
                self.model = PPO.load(str(self.model_path))
                logger.info("Successfully loaded PPO model from %s", self.model_path)
                return True
            except Exception as exc:
                logger.warning("Failed to load PPO model (%s). Using heuristic fallback.", exc)
                self.model = None
                return False
        return False

    def decide(
        self,
        satellite: SatelliteState,
        environment: EnvironmentData,
        channel: OpticalChannelState,
        qkd: QKDMetrics
    ) -> ControlAction:
        """Compute control action via PPO policy network or fallback."""
        if not satellite.is_visible or satellite.elevation_deg < settings.MIN_ELEVATION:
            self.power_pct = settings.MIN_TRANSMISSION_POWER
            self.photon_rate_norm = settings.MIN_PHOTON_RATE
            self.beam_divergence_norm = 0.30
            return ControlAction(
                transmission_power_pct=self.power_pct,
                photon_rate_norm=self.photon_rate_norm,
                beam_divergence_norm=self.beam_divergence_norm,
                controller_type="PPO",
                reason="Satellite below line-of-sight threshold; link idle"
            )

        # If trained model is available, use neural network policy
        if self.model is not None:
            try:
                obs = self._build_observation(satellite, environment, channel, qkd)
                action, _states = self.model.predict(obs, deterministic=True)
                action = np.clip(action, -1.0, 1.0)

                delta_p = float(action[0] * (self.rate_limit * 100.0))
                delta_r = float(action[1] * self.rate_limit)
                delta_d = float(action[2] * self.rate_limit)

                self.power_pct = float(np.clip(self.power_pct + delta_p, settings.MIN_TRANSMISSION_POWER, settings.MAX_TRANSMISSION_POWER))
                self.photon_rate_norm = float(np.clip(self.photon_rate_norm + delta_r, settings.MIN_PHOTON_RATE, settings.MAX_PHOTON_RATE))
                self.beam_divergence_norm = float(np.clip(self.beam_divergence_norm + delta_d, settings.MIN_BEAM_DIVERGENCE, settings.MAX_BEAM_DIVERGENCE))

                return ControlAction(
                    transmission_power_pct=round(self.power_pct, 2),
                    photon_rate_norm=round(self.photon_rate_norm, 4),
                    beam_divergence_norm=round(self.beam_divergence_norm, 4),
                    controller_type="PPO",
                    reason="PPO continuous neural policy inference"
                )
            except Exception as exc:
                logger.error("PPO inference failed (%s). Falling back to rule-based decision.", exc)

        # Fallback to rule-based controller
        rule_action = self.fallback_controller.decide(satellite, environment, channel, qkd)
        self.power_pct = rule_action.transmission_power_pct
        self.photon_rate_norm = rule_action.photon_rate_norm
        self.beam_divergence_norm = rule_action.beam_divergence_norm

        return ControlAction(
            transmission_power_pct=rule_action.transmission_power_pct,
            photon_rate_norm=rule_action.photon_rate_norm,
            beam_divergence_norm=rule_action.beam_divergence_norm,
            controller_type="PPO",
            reason=f"PPO (Prior Heuristic): {rule_action.reason}"
        )

    def _build_observation(
        self,
        sat: SatelliteState,
        env: EnvironmentData,
        channel: OpticalChannelState,
        qkd: QKDMetrics
    ) -> np.ndarray:
        """Construct normalized observation matching QSATEnvironment shape."""
        elev_norm = max(0.0, min(1.0, (sat.elevation_deg + 10.0) / 100.0))
        range_norm = max(0.0, min(1.0, sat.slant_range_km / 2000.0))
        temp_norm = max(0.0, min(1.0, (env.temperature + 20.0) / 70.0))
        hum_norm = env.humidity / 100.0
        light_norm = max(0.0, min(1.0, env.ambient_light / 100000.0))
        vib_norm = max(0.0, min(1.0, env.vibration / 2.0))
        cloud_norm = env.cloud_factor
        turb_norm = env.turbulence
        loss_norm = max(0.0, min(1.0, channel.total_loss_db / 60.0))
        qber_norm = max(0.0, min(1.0, qkd.qber / 0.50))
        skr_norm = max(0.0, min(1.0, qkd.secret_key_rate / 30000.0))
        rx_norm = max(0.0, min(1.0, channel.received_photon_rate / 500000.0))
        pwr_norm = self.power_pct / 100.0
        rate_norm = self.photon_rate_norm
        div_norm = self.beam_divergence_norm

        return np.array([
            elev_norm, range_norm, temp_norm, hum_norm, light_norm,
            vib_norm, cloud_norm, turb_norm, loss_norm, qber_norm,
            skr_norm, rx_norm, pwr_norm, rate_norm, div_norm
        ], dtype=np.float32)
