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
from ai.model_validator import repair_nested_archive, sanitize_environment_for_sb3, validate_ppo_archive
from ai.rule_based_controller import RuleBasedController
from ai.spaces import apply_action_deltas, build_normalized_observation

logger = logging.getLogger("qsat.ppo_controller")


class PPOController:
    """Uses a trained PPO neural policy to output continuous actions.
    
    Strictly distinguishes requested vs actual controller and prevents unacknowledged fallback.
    In evaluation mode, fails explicitly when PPO cannot load or predict.
    """

    def __init__(
        self,
        model_path: Optional[str] = "models/ppo_qsat.zip",
        evaluation_mode: bool = False,
        auto_repair: bool = True
    ):
        self.model_path = Path(model_path) if model_path else None
        self.evaluation_mode = evaluation_mode
        self.auto_repair = auto_repair
        self.model = None
        self.model_loaded = False
        self.load_error: Optional[str] = None
        self.fallback_controller = RuleBasedController()

        # Actuator State
        self.power_pct: float = 50.0
        self.photon_rate_norm: float = 0.70
        self.beam_divergence_norm: float = 0.25
        self.rate_limit = settings.MAX_RATE_OF_CHANGE

        self._load_model_if_available()

    def _load_model_if_available(self) -> bool:
        """Attempt loading trained Stable-Baselines3 PPO model with archive validation."""
        if not self.model_path or not self.model_path.exists():
            self.load_error = f"Model file not found at {self.model_path}"
            logger.warning(self.load_error)
            if self.evaluation_mode:
                raise FileNotFoundError(self.load_error)
            return False

        # Validate archive integrity
        report = validate_ppo_archive(self.model_path)
        if not report.is_loadable:
            if report.is_nested and self.auto_repair:
                logger.info("PPO model archive at %s is nested. Auto-repairing while preserving original...", self.model_path)
                try:
                    report = repair_nested_archive(self.model_path, self.model_path, backup_original=True)
                except Exception as exc:
                    self.load_error = f"Auto-repair failed: {exc}"
                    logger.error(self.load_error)
                    if self.evaluation_mode:
                        raise RuntimeError(self.load_error)
                    return False
            else:
                self.load_error = f"Model archive invalid or missing root files: {report.error_message or report.missing_files}"
                logger.warning(self.load_error)
                if self.evaluation_mode:
                    raise ValueError(self.load_error)
                return False

        try:
            sanitize_environment_for_sb3()
            from stable_baselines3 import PPO
            self.model = PPO.load(str(self.model_path))
            self.model_loaded = True
            self.load_error = None
            logger.info("Successfully loaded PPO model from %s (SB3 version: %s)", self.model_path, report.sb3_version)
            return True
        except Exception as exc:
            self.load_error = f"Failed to instantiate PPO from {self.model_path}: {exc}"
            logger.warning(self.load_error)
            self.model = None
            self.model_loaded = False
            if self.evaluation_mode:
                raise RuntimeError(self.load_error)
            return False

    def decide(
        self,
        satellite: SatelliteState,
        environment: EnvironmentData,
        channel: OpticalChannelState,
        qkd: QKDMetrics
    ) -> ControlAction:
        """Compute control action via PPO policy network or explicit fallback."""
        # 1. Line-of-sight threshold check
        if not satellite.is_visible or satellite.elevation_deg < settings.MIN_ELEVATION:
            self.power_pct = settings.MIN_TRANSMISSION_POWER
            self.photon_rate_norm = settings.MIN_PHOTON_RATE
            self.beam_divergence_norm = 0.30
            return ControlAction(
                transmission_power_pct=self.power_pct,
                photon_rate_norm=self.photon_rate_norm,
                beam_divergence_norm=self.beam_divergence_norm,
                requested_controller="PPO",
                actual_controller="PPO",
                controller_type="PPO",
                model_loaded=self.model_loaded,
                fallback_reason=None,
                reason="Satellite below line-of-sight threshold; link idle"
            )

        # 2. If model is loaded, run neural policy
        if self.model is not None:
            try:
                obs = build_normalized_observation(
                    satellite=satellite,
                    environment=environment,
                    channel=channel,
                    qkd=qkd,
                    current_power_pct=self.power_pct,
                    current_photon_rate_norm=self.photon_rate_norm,
                    current_beam_divergence_norm=self.beam_divergence_norm
                )
                action, _states = self.model.predict(obs, deterministic=True)
                new_p, new_r, new_d, dp, dr, dd = apply_action_deltas(
                    action=action,
                    current_power_pct=self.power_pct,
                    current_photon_rate_norm=self.photon_rate_norm,
                    current_beam_divergence_norm=self.beam_divergence_norm,
                    rate_limit=self.rate_limit
                )

                self.power_pct = new_p
                self.photon_rate_norm = new_r
                self.beam_divergence_norm = new_d

                return ControlAction(
                    transmission_power_pct=round(self.power_pct, 2),
                    photon_rate_norm=round(self.photon_rate_norm, 4),
                    beam_divergence_norm=round(self.beam_divergence_norm, 4),
                    requested_controller="PPO",
                    actual_controller="PPO",
                    controller_type="PPO",
                    model_loaded=True,
                    fallback_reason=None,
                    reason="PPO continuous neural policy inference"
                )
            except Exception as exc:
                inference_err = f"PPO inference failed: {exc}"
                logger.error(inference_err)
                if self.evaluation_mode:
                    raise RuntimeError(inference_err)
                # In non-evaluation mode, proceed to explicit fallback below
                fallback_reason = inference_err
        else:
            if self.evaluation_mode:
                raise RuntimeError(f"PPO evaluation failed: Model not loaded ({self.load_error})")
            fallback_reason = f"PPO model not loaded: {self.load_error}"

        # 3. Explicit Fallback to Rule-Based Controller (NEVER reported as genuine PPO)
        rule_action = self.fallback_controller.decide(satellite, environment, channel, qkd)
        self.power_pct = rule_action.transmission_power_pct
        self.photon_rate_norm = rule_action.photon_rate_norm
        self.beam_divergence_norm = rule_action.beam_divergence_norm

        return ControlAction(
            transmission_power_pct=rule_action.transmission_power_pct,
            photon_rate_norm=rule_action.photon_rate_norm,
            beam_divergence_norm=rule_action.beam_divergence_norm,
            requested_controller="PPO",
            actual_controller="RULE_BASED",
            controller_type="RULE_BASED",
            model_loaded=False,
            fallback_reason=fallback_reason,
            reason=f"FALLBACK to Rule-Based: {fallback_reason} | Heuristic: {rule_action.reason}"
        )
